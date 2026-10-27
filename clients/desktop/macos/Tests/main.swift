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
// The desktop pins its loopback port so the page origin (and the browser storage attached to it) stays
// stable across reloads and relaunches; an EXO_DESKTOP_PORT override still wins.
unsetenv("EXO_DESKTOP_PORT")
try fixture("trap '' INT TERM; printf '%s' \"$*\" > \"" + temp.path + "/argv\"; printf 'http://127.0.0.1:7342/#token=porttest\\n'; while :; do sleep 1; done\n")
let pinned = ExoWebLauncher()
let pinnedReady = DispatchSemaphore(value: 0)
pinned.start { _ in pinnedReady.signal() }
check(pinnedReady.wait(timeout: .now() + 3) == .success, "pinned startup")
check((try? String(contentsOfFile: temp.path + "/argv", encoding: .utf8))?.contains("--port 7342") == true, "pinned port 7342 without override")
let pinnedStopped = DispatchSemaphore(value: 0)
pinned.stopWebServer { pinnedStopped.signal() }
check(pinnedStopped.wait(timeout: .now() + 5) == .success, "pinned shutdown")
setenv("EXO_DESKTOP_PORT", "7355", 1)
try fixture("trap '' INT TERM; printf '%s' \"$*\" > \"" + temp.path + "/argv\"; printf 'http://127.0.0.1:7355/#token=porttest\\n'; while :; do sleep 1; done\n")
let overridden = ExoWebLauncher()
let overriddenReady = DispatchSemaphore(value: 0)
overridden.start { _ in overriddenReady.signal() }
check(overriddenReady.wait(timeout: .now() + 3) == .success, "override startup")
check((try? String(contentsOfFile: temp.path + "/argv", encoding: .utf8))?.contains("--port 7355") == true, "override port wins")
let overriddenStopped = DispatchSemaphore(value: 0)
overridden.stopWebServer { overriddenStopped.signal() }
check(overriddenStopped.wait(timeout: .now() + 5) == .success, "override shutdown")
unsetenv("EXO_DESKTOP_PORT")
print("PASS: complete URL, single completion, pipe drain, later exit, bounded shutdown, pinned port")
