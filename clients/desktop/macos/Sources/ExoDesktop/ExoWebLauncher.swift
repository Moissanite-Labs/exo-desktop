import Foundation
import Darwin

/// Starts `exo web` and returns its page address.
///
/// The page address carries a token in its fragment. This class keeps that
/// address in memory only. It never prints it, never logs it, and never
/// writes it to disk. Error messages name the failure, not the address.
final class ExoWebLauncher: @unchecked Sendable {
    enum LaunchError: Error, CustomStringConvertible {
        case exoNotFound
        case bundledRuntimeDamaged
        case invalidOverride(String)
        case launchFailed
        case timedOut
        case exited(Int32)

        var description: String {
            switch self {
            case .exoNotFound:
                return "No `exo` binary was found on PATH. Install Exo first, or set EXO_DESKTOP_EXO."
            case .bundledRuntimeDamaged:
                return "The bundled desktop runtime is missing or damaged. Reinstall the app; it does not use the source checkout."
            case .invalidOverride(let path):
                return "EXO_DESKTOP_EXO points to \(path), which is not executable."
            case .launchFailed:
                return "`exo web` could not be started."
            case .timedOut:
                return "`exo web` did not print a page address within 30 seconds."
            case .exited(let code):
                if code == 69 { return "The selected core socket is unavailable. Start that core separately, then retry. The desktop will not start a replacement core." }
                if code == 72 { return "The bundled desktop runtime is missing, damaged, or version-mismatched. Reinstall the app; it does not fall back to the source checkout." }
                if code == 1 {
                    return "`exo web` exited. Its port may already be in use. Use the page that is already open, or set EXO_DESKTOP_PORT to a free port."
                }
                return "`exo web` exited with code \(code)."
            }
        }
    }

    private var process: Process?
    private var outputPipe: Pipe?
    private var errorPipe: Pipe?
    private var output = ""
    private var finished = false
    private var hasPage = false
    private var stopping = false
    var onExit: ((Int32) -> Void)?

    private var environment: [String: String] {
        var env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        env["PATH"] = [home + "/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", env["PATH"] ?? "", "/usr/bin", "/bin"].joined(separator: ":")
        env["PYTHONUNBUFFERED"] = "1"
        return env
    }
    private var startCompletion: ((Result<URL, LaunchError>) -> Void)?
    private let lock = NSLock()

    func start(completion: @escaping (Result<URL, LaunchError>) -> Void) {
        // A bundled launcher that exists but is not executable is damaged,
        // not absent. Falling through to a PATH `exo` here would silently
        // run whatever checkout venv happens to be installed, which is
        // exactly the failure this packaging work removes.
        if (ProcessInfo.processInfo.environment["EXO_DESKTOP_EXO"] ?? "").isEmpty,
           let bundled = Bundle.main.resourceURL?.appendingPathComponent("exo-alpha"),
           FileManager.default.fileExists(atPath: bundled.path),
           !FileManager.default.isExecutableFile(atPath: bundled.path) {
            completion(.failure(.bundledRuntimeDamaged))
            return
        }
        if let override = ProcessInfo.processInfo.environment["EXO_DESKTOP_EXO"],
           !override.isEmpty,
           !FileManager.default.isExecutableFile(atPath: override) {
            completion(.failure(.invalidOverride(override)))
            return
        }
        guard let exo = findExo() else {
            completion(.failure(.exoNotFound))
            return
        }
        // Stored, not captured: the handlers below run in Sendable contexts,
        // so they must capture only self (Sendable), never the completion
        // itself. finish() takes it out under lock and calls it once.
        // Marking the parameter @Sendable instead would move the same
        // problem to the caller, which captures the web view.
        lock.lock()
        startCompletion = completion
        lock.unlock()
        let port = ProcessInfo.processInfo.environment["EXO_DESKTOP_PORT"]
            .flatMap(Int.init) ?? (exo.lastPathComponent == "exo-alpha" ? 0 : 7342)
        let process = Process()
        process.executableURL = exo
        process.arguments = ["web", "--port", "\(port)", "--no-open"]
        process.environment = environment
        process.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        self.process = process
        self.outputPipe = outputPipe
        self.errorPipe = errorPipe

        // Drain stderr so a full pipe cannot stall the server. Its content
        // is never shown, because it must not become a place a token leaks.
        errorPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }
        outputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            guard let self = self else { return }
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            self.lock.lock()
            self.output += text
            if self.output.count > 8192 {
                self.output = String(self.output.suffix(8192))
            }
            let complete = self.output.components(separatedBy: "\n").dropLast().joined(separator: "\n")
            let page = self.pageURL(from: complete)
            self.lock.unlock()
            if let page = page {
                self.finish(with: .success(page))
            }
        }
        process.terminationHandler = { [weak self] proc in
            guard let self = self else { return }
            self.lock.lock()
            let started = self.hasPage
            let stopping = self.stopping
            self.lock.unlock()
            self.finish(with: .failure(.exited(proc.terminationStatus)))
            self.clearPipes()
            if started && !stopping { self.onExit?(proc.terminationStatus) }
        }
        do {
            try process.run()
        } catch {
            clearPipes()
            finish(with: .failure(.launchFailed))
            return
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + 30) { [weak self] in
            guard let self = self else { return }
            self.lock.lock()
            let alreadyFinished = self.finished
            self.lock.unlock()
            guard !alreadyFinished else { return }
            self.process?.terminate()
            self.finish(with: .failure(.timedOut))
        }
    }

    /// Stops the web server, then calls completion. The core keeps running.
    /// Sends SIGINT, waits up to five seconds on a semaphore, then forces
    /// termination if the server is still running.
    func stopWebServer(completion: @Sendable @escaping () -> Void) {
        guard let proc = process, proc.isRunning else {
            completion()
            return
        }
        lock.lock()
        stopping = true
        lock.unlock()
        DispatchQueue.global().async {
            proc.interrupt()
            self.wait(proc, seconds: 2)
            if proc.isRunning { proc.terminate() }
            self.wait(proc, seconds: 1)
            if proc.isRunning { kill(proc.processIdentifier, SIGKILL) }
            self.wait(proc, seconds: 1)
            self.clearPipes()
            completion()
        }
    }

    private func wait(_ proc: Process, seconds: Double) {
        let deadline = Date().addingTimeInterval(seconds)
        while proc.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.02) }
    }

    /// Stops the background core. Runs `exo stop` once.
    func stopCore(completion: @Sendable @escaping (Int32) -> Void) {
        guard let exo = findExo() else {
            completion(127)
            return
        }
        DispatchQueue.global().async {
            let process = Process()
            process.executableURL = exo
            process.arguments = ["stop"]
            process.environment = self.environment
            process.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
            process.standardOutput = FileHandle.nullDevice
            process.standardError = FileHandle.nullDevice
            do {
                try process.run()
                self.wait(process, seconds: 5)
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
                self.wait(process, seconds: 1)
                completion(process.isRunning ? 1 : process.terminationStatus)
            } catch {
                completion(1)
            }
        }
    }

    private func finish(with result: Result<URL, LaunchError>) {
        lock.lock()
        guard !finished else {
            lock.unlock()
            return
        }
        finished = true
        if case .success = result { hasPage = true }
        output = ""
        let completion = startCompletion
        startCompletion = nil
        lock.unlock()
        completion?(result)
    }

    private func clearPipes() {
        outputPipe?.fileHandleForReading.readabilityHandler = nil
        errorPipe?.fileHandleForReading.readabilityHandler = nil
    }

    private func pageURL(from text: String) -> URL? {
        for word in text.components(separatedBy: .whitespacesAndNewlines) {
            let candidate = String(word)
            guard candidate.hasPrefix("http://127.0.0.1:")
                || candidate.hasPrefix("http://localhost:") else { continue }
            guard candidate.contains("/#token=") else { continue }
            if let url = URL(string: candidate) {
                return url
            }
        }
        return nil
    }

    private func findExo() -> URL? {
        if let override = ProcessInfo.processInfo.environment["EXO_DESKTOP_EXO"],
           !override.isEmpty {
            return URL(fileURLWithPath: override)
        }
        let bundled = Bundle.main.resourceURL?.appendingPathComponent("exo-alpha")
        if let bundled, FileManager.default.isExecutableFile(atPath: bundled.path) { return bundled }
        let path = environment["PATH"] ?? ""
        for dir in path.split(separator: ":") {
            let candidate = URL(fileURLWithPath: String(dir)).appendingPathComponent("exo")
            if FileManager.default.isExecutableFile(atPath: candidate.path) {
                return candidate
            }
        }
        for dir in ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"] {
            let candidate = URL(fileURLWithPath: dir).appendingPathComponent("exo")
            if FileManager.default.isExecutableFile(atPath: candidate.path) {
                return candidate
            }
        }
        return nil
    }
}
