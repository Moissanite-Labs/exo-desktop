"""Exercise production preference bridge with a disposable WKWebView and fixture HTTP server."""

import os
import http.server
import pathlib
import subprocess
import tempfile
import threading
import uuid

root = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<html><body>Disposable preference fixture</body></html>")

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="exo-native-prefs-") as directory:
        temp = pathlib.Path(directory)
        source = (
            (root / "Sources/ExoDesktop/main.swift")
            .read_text()
            .split("\nlet delegate = AppDelegate()")[0]
        )
        source += (root / "Tests/NativePreferencesAcceptance.swift").read_text()
        (temp / "main.swift").write_text(source)
        subprocess.run(
            [
                "swiftc",
                str(temp / "main.swift"),
                str(root / "Sources/ExoDesktop/ExoWebLauncher.swift"),
                str(root / "Sources/ExoDesktop/DesktopPreferences.swift"),
                "-framework",
                "AppKit",
                "-framework",
                "WebKit",
                "-o",
                str(temp / "probe"),
            ],
            check=True,
        )
        suite = "exo-prefs-fixture-" + uuid.uuid4().hex
        home = temp / "home"
        home.mkdir()
        environment = dict(os.environ, HOME=str(home), CFFIXED_USER_HOME=str(home))
        subprocess.run(
            [
                str(temp / "probe"),
                f"http://127.0.0.1:{server.server_port}/",
                suite,
                "seed",
            ],
            env=environment,
            check=True,
            timeout=45,
        )
        second = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=second.serve_forever, daemon=True).start()
        try:
            assert second.server_port != server.server_port
            subprocess.run(
                [
                    str(temp / "probe"),
                    f"http://127.0.0.1:{second.server_port}/",
                    suite,
                    "restore",
                ],
                env=environment,
                check=True,
                timeout=45,
            )
        finally:
            second.shutdown()
finally:
    server.shutdown()
