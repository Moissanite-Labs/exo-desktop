"""Desktop interface-state restoration (issue 30): the pure preference module, run in node.

The page's saved choices are the only thing persisted for restoration: a view, a thread id, a layout
and a transcript scroll fraction. Conversations and memory stay in the core, and the page access token
must never survive a save. The browser copy lives in localStorage (one origin, one port); the desktop
app injects a port-independent copy as window.__exoDesktopPrefs, which fills only the keys the browser
copy does not have — that is what restores state when the page moves to a new port.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "exo_command" / "static"
NODE = shutil.which("node")


def node(tmp_path, body):
    (tmp_path / "desktop_state.mjs").write_text((STATIC / "desktop_state.js").read_text(encoding="utf-8"))
    (tmp_path / "t.mjs").write_text('import * as d from "./desktop_state.mjs";\n' + body)
    out = subprocess.run([NODE, str(tmp_path / "t.mjs")], capture_output=True, text=True, timeout=20, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_cleaning_keeps_only_restoration_keys_and_drops_tokens(tmp_path):
    got = node(tmp_path, '''
const mem = () => { const m = {}; return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = v; } }; };
const s = mem();
const cleaned = d.writeState(s, { view: "tasks", thread: "s1", layout: "classic", scroll: 0.25,
  token: "SECRET-TOKEN", code: "SECRET-CODE", url: "http://127.0.0.1:7342/#token=SECRET-TOKEN",
  fragment: "#token=SECRET-TOKEN", session: "s1" }, null);
const stored = JSON.parse(s.getItem("xc-desktop-state"));
console.log(JSON.stringify({ cleaned, stored, leaked: JSON.stringify(stored).includes("SECRET") }));
''')
    assert got["cleaned"] == {"view": "tasks", "thread": "s1", "layout": "classic", "scroll": 0.25}
    assert got["stored"] == got["cleaned"]
    assert got["leaked"] is False


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_merge_prefers_browser_copy_and_injected_copy_fills_gaps(tmp_path):
    got = node(tmp_path, '''
const mem = () => { const m = {}; return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = v; } }; };
// Port changed: the browser copy at the new origin is empty, the injected app copy restores everything.
const empty = mem();
const moved = d.readState(empty, { view: "providers", thread: "s9", layout: "classic", scroll: 0.5 });
// Same origin: the browser copy wins key by key, the injected copy only fills what is missing.
const s = mem();
s.setItem("xc-desktop-state", JSON.stringify({ thread: "s2" }));
const same = d.readState(s, { view: "tasks", thread: "s9", layout: "classic", scroll: 0.5 });
// Junk in either copy is dropped, never trusted.
const junk = d.readState(mem(), { view: "nowhere", thread: "", layout: "sideways", scroll: 9, token: "x" });
console.log(JSON.stringify({ moved, same, junk }));
''')
    assert got["moved"] == {"view": "providers", "thread": "s9", "layout": "classic", "scroll": 0.5}
    assert got["same"] == {"thread": "s2", "view": "tasks", "layout": "classic", "scroll": 0.5}
    assert got["junk"] == {}


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_pick_thread_returns_picker_for_a_removed_thread(tmp_path):
    got = node(tmp_path, '''
const sessions = [{ id: "s1" }, { id: "s2" }];
console.log(JSON.stringify({
  kept: d.pickThread("s2", sessions),
  removed: d.pickThread("gone", sessions),
  first: d.pickThread(undefined, sessions),
  none: d.pickThread(undefined, []),
}));
''')
    assert got == {"kept": "s2", "removed": None, "first": "s1", "none": None}


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_scroll_fraction_is_clamped_and_round_trips(tmp_path):
    got = node(tmp_path, '''
console.log(JSON.stringify({
  mid: d.scrollFraction(1000, 5000, 700),
  top: d.scrollFraction(-50, 5000, 700),
  bottom: d.scrollFraction(99999, 5000, 700),
  flat: d.scrollFraction(10, 300, 700),
  back: d.scrollTopFor(0.25, 5000, 700),
}));
''')
    assert got["mid"] == pytest.approx(1000 / 4300)
    assert got["top"] == 0 and got["bottom"] == 1 and got["flat"] == 0
    assert got["back"] == pytest.approx(1075.0)


def test_chat_and_app_use_the_desktop_state_module():
    chat = (STATIC / "chat.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'from "./desktop_state.js"' in chat and 'from "./desktop_state.js"' in app
    assert "pickThread(saved.thread, sessions)" in chat
    assert "restoreScroll" in chat and "scrollFraction(" in chat and "scrollTopFor(" in chat
    assert "window.__exoDesktopPrefs" in app and "window.__exoDesktopPrefs" in chat
    # The token lives in sessionStorage and in the URL fragment only; the new module must not name it
    # as something it stores, and neither view may write it into the preference key.
    state = (STATIC / "desktop_state.js").read_text(encoding="utf-8")
    assert "xc-token" not in state and "sessionStorage" not in state
    assert "token" in state  # only as a dropped key in cleanPrefs / the doc comment
