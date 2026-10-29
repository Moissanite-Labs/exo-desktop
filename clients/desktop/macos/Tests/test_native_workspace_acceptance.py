"""Local composition acceptance: real WKWebView, fixture core/API, no installation or live data."""

import os, pathlib, subprocess, tempfile, uuid, sys, asyncio

root = pathlib.Path(__file__).resolve().parents[4]
sys.path[:0] = [
    str(root / "src"),
    str(root / "plugins/exo-command"),
    str(root / "plugins/exo-command/tests"),
]
from exo_command import api
from browser import Served
from test_pet_web import PetSource
from test_layout_web import parts

LIVE = {
    "id": "native-incoming",
    "role": "assistant",
    "content": parts("native incoming during restore"),
}


class NativeSource(PetSource):
    def __init__(self):
        super().__init__()
        self.live = False

    async def call(self, body):
        data = await super().call(body)
        if type(body).TYPE == "session.list":
            data["sessions"] = data["sessions"][
                :1
            ]  # remembered s2 is outside this bounded prefix
        if type(body).TYPE == "session.get":
            data["session"]["id"] = body.session
            data["messages"][0]["content"] = parts("native snapshot " + body.session)
            if self.live:
                data["seq"] = 1
                if body.session == "s2":
                    data["messages"].append(LIVE)
        return data


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
    release = temp / "release-list"
    release_panels = temp / "release-panels"
    real_dispatch = api.dispatch

    async def dispatch(centre, method, path, query, body):
        if method == "GET" and path == "/api/chat/panels":
            while not release_panels.exists():
                await asyncio.sleep(0.02)
        if method == "GET" and path == "/api/chat/sessions" and not release.exists():
            return 503, {"error": "Synthetic initial list unavailable"}
        if method == "GET" and path == "/api/chat/sessions/s2" and not src.live:
            snapshot = await real_dispatch(centre, method, path, query, body)
            src.live = (
                True  # later snapshots include what the fixture core now recorded
            )
            centre.record(
                {
                    "seq": 1,
                    "type": "message.completed",
                    "session": "s2",
                    "body": {"message": LIVE},
                }
            )
            await asyncio.sleep(
                0.2
            )  # deliver the live event while the older snapshot remains held
            return snapshot
        return await real_dispatch(centre, method, path, query, body)

    api.dispatch = dispatch
    for phase in ["list-failure", "restore"]:
        src = NativeSource()
        src.pairs = 70
        srv = Served(src)
        try:
            ports.append(srv.port)
            url = srv.url().replace("&chat", "")
            subprocess.run(
                [
                    str(temp / "probe"),
                    url,
                    suite,
                    phase,
                    str(release),
                    str(release_panels),
                ],
                env=env,
                check=True,
                timeout=180,
            )
            assert not any(kind == "turn.send" for kind, _ in src.calls)
        finally:
            srv.close()
    api.dispatch = real_dispatch
    assert len(set(ports)) == 2, ports
    print(
        "PASS composed native workspace: same-process reload and separate-process relaunch across ports",
        ports,
    )
