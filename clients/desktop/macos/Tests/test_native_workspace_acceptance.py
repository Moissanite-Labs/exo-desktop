"""Local composition acceptance: real WKWebView, fixture core/API, no installation or live data."""

import os, pathlib, subprocess, tempfile, uuid, sys

root = pathlib.Path(__file__).resolve().parents[4]
sys.path[:0] = [
    str(root / "src"),
    str(root / "plugins/exo-command"),
    str(root / "plugins/exo-command/tests"),
]
from browser import Served
from test_pet_web import PetSource

with tempfile.TemporaryDirectory(prefix="exo-composed-wk-") as directory:
    temp = pathlib.Path(directory)
    home = temp / "home"
    home.mkdir()
    native = root / "clients/desktop/macos/Sources/ExoDesktop"
    source = (native / "main.swift").read_text().split(
        "\nlet delegate = AppDelegate()"
    )[0] + (
        pathlib.Path(__file__).resolve().parent / "NativeWorkspaceAcceptance.swift"
    ).read_text()
    (temp / "main.swift").write_text(source)
    subprocess.run(
        [
            "swiftc",
            str(temp / "main.swift"),
            *[
                str(path)
                for path in sorted(native.glob("*.swift"))
                if path.name != "main.swift"
            ],
            "-framework",
            "AppKit",
            "-framework",
            "WebKit",
            "-o",
            str(temp / "probe"),
        ],
        check=True,
    )
    suite = "exo-composed-wk-" + uuid.uuid4().hex
    env = dict(
        os.environ,
        HOME=str(home),
        CFFIXED_USER_HOME=str(home),
        EXO_BUS_URL="http://127.0.0.1:9",
    )
    ports = []
    for phase in ["seed", "restore"]:
        src = PetSource()
        src.pairs = 70
        srv = Served(src)
        try:
            ports.append(srv.port)
            url = srv.url().replace("&chat", "")
            subprocess.run(
                [str(temp / "probe"), url, suite, phase],
                env=env,
                check=True,
                timeout=180,
            )
            assert not any(kind == "turn.send" for kind, _ in src.calls)
        finally:
            srv.close()
    assert len(set(ports)) == 2, ports
    print(
        "PASS composed native workspace: same-process reload and separate-process relaunch across ports",
        ports,
    )
