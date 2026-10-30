import Foundation
import Darwin
let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try FileManager.default.createDirectory(at: temp, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: temp) }
let fake = temp.appendingPathComponent("fake exo")
func fixture(_ script: String) throws {
    try ("#!/bin/sh\n" + script).write(to: fake, atomically: true, encoding: .utf8)
    chmod(fake.path, 0o755)
    setenv("EXO_DESKTOP_EXO", fake.path, 1)
}
func check(_ condition: Bool, _ message: String) {
    if !condition { fputs("FAIL: \(message)\n", stderr); exit(1) }
}
// Simulate Finder's sparse PATH and root working directory.
setenv("PATH", "/usr/bin:/bin", 1)
FileManager.default.changeCurrentDirectoryPath("/")
try fixture("[ \"$PWD\" = \"$HOME\" ] || exit 91; case \"$PATH\" in *\"$HOME/.local/bin\"*) ;; *) exit 92;; esac; printf 'http://127.0.0.1:7342/#token=part'; sleep 0.2; printf 'complete\\n'; dd if=/dev/zero bs=65536 count=32 2>/dev/null; dd if=/dev/zero bs=65536 count=32 >&2 2>/dev/null; exit 17\n")
let launcher = ExoWebLauncher()
let started = DispatchSemaphore(value: 0)
let exited = DispatchSemaphore(value: 0)
var callbacks = 0
launcher.onExit = { code in check(code == 17, "later exit status"); exited.signal() }
launcher.start { result in
    callbacks += 1
    if case .success(let url) = result { check(url.fragment == "token=partcomplete", "complete URL line") }
    else { check(false, "startup") }
    started.signal()
}
check(started.wait(timeout: .now() + 3) == .success, "startup deadline")
check(exited.wait(timeout: .now() + 5) == .success, "both pipes continuously drained and later exit delivered")
check(callbacks == 1, "single startup completion")
try fixture("trap '' INT TERM; printf 'http://127.0.0.1:7342/#token=localtest\\n'; while :; do sleep 1; done\n")
let stubborn = ExoWebLauncher()
let ready = DispatchSemaphore(value: 0)
stubborn.start { _ in ready.signal() }
check(ready.wait(timeout: .now() + 3) == .success, "stubborn startup")
let stopped = DispatchSemaphore(value: 0)
let before = Date()
stubborn.stopWebServer { stopped.signal() }
check(stopped.wait(timeout: .now() + 5) == .success, "bounded SIGKILL shutdown")
check(Date().timeIntervalSince(before) < 5, "shutdown elapsed bound")

// A stuck startup must be reaped before Retry is offered, even if it ignores
// graceful signals. The timeout, not the signal's exit status, is reported.
let pidFile = temp.appendingPathComponent("stuck.pid")
try fixture("trap '' INT TERM; echo $$ > '\(pidFile.path)'; while :; do sleep 1; done\n")
let stuck = ExoWebLauncher(startupTimeout: 0.5)
let timedOut = DispatchSemaphore(value: 0)
let simultaneousStop = DispatchSemaphore(value: 0)
var timeoutCallbacks = 0
stuck.onExit = { _ in check(false, "timed-out startup must not report a later exit") }
stuck.start { result in
    timeoutCallbacks += 1
    guard case .failure(.timedOut) = result else { check(false, "timeout result"); return }
    guard let pidText = try? String(contentsOf: pidFile, encoding: .utf8),
          let pid = Int32(pidText.trimmingCharacters(in: .whitespacesAndNewlines)) else {
        check(false, "stuck fixture pid"); return
    }
    check(kill(pid, 0) == -1 && errno == ESRCH, "stuck child exited before timeout completion")
    timedOut.signal()
}
// Quitting during timeout cleanup joins the same shutdown instead of sending
// signals concurrently to the same Process.
DispatchQueue.global().asyncAfter(deadline: .now() + 0.8) {
    stuck.stopWebServer { simultaneousStop.signal() }
}
check(timedOut.wait(timeout: .now() + 6) == .success, "bounded timeout cleanup")
check(simultaneousStop.wait(timeout: .now() + 1) == .success, "concurrent stop completion")
Thread.sleep(forTimeInterval: 0.2)
check(timeoutCallbacks == 1, "single timeout completion")

try fixture("printf 'http://127.0.0.1:7342/#token=ready\\n'; exec sleep 10\n")
let fast = ExoWebLauncher(startupTimeout: 0.5)
let fastReady = DispatchSemaphore(value: 0)
fast.onExit = { _ in check(false, "deadline must not stop a successful launch") }
fast.start { result in
    guard case .success = result else { check(false, "fast startup"); return }
    fastReady.signal()
}
check(fastReady.wait(timeout: .now() + 3) == .success, "fast startup deadline")
Thread.sleep(forTimeInterval: 0.8)
let fastStopped = DispatchSemaphore(value: 0)
fast.stopWebServer { fastStopped.signal() }
check(fastStopped.wait(timeout: .now() + 5) == .success, "stop successful launch")
print("PASS: complete URL, single completion, pipe drain, later exit, bounded shutdown and timeout cleanup")
