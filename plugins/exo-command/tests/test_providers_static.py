"""Static checks on the web client's provider setup code: a key must never reach storage, logs or the URL."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "exo_command" / "static"


def text(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_key_field_is_a_password_input_that_is_not_saved():
    js = text("providers.js")
    assert 'type: "password"' in js
    assert 'autocomplete: "new-password"' in js
    assert 'spellcheck: "false"' in js
    assert not re.search(r"\bname:\s*\"", js)           # no name attribute for a password manager to key on


def test_no_local_storage_anywhere():
    for f in STATIC.glob("*.js"):
        body = f.read_text(encoding="utf-8")
        if f.name == "layout.js":  # D-046: the one exception, the layout choice. It never sees keys or text.
            assert "setItem(KEY" in body.replace("(store || localStorage).setItem(KEY", "setItem(KEY") and 'const KEY = "xc-layout"' in body
            continue
        assert "localStorage" not in body, f.name


def test_session_storage_only_for_the_token_in_provider_code():
    for name in ("providers.js", "dom.js"):
        for m in re.finditer(r"sessionStorage\.\w+\(([^)]*)\)", text(name)):
            assert m.group(1).strip().startswith('"xc-token"'), (name, m.group(0))
    for m in re.finditer(r"sessionStorage\.setItem\(([^,)]*)", text("app.js")):
        assert m.group(1).strip() in ('"xc-token"', '"xc-booted"')


def test_providers_js_never_logs():
    js = text("providers.js")
    assert "console." not in js


def test_key_field_is_cleared_before_the_request():
    js = text("providers.js")
    body = js[js.index("async function save"):js.index("async function test")]
    assert 'input.value = ""' in body
    assert body.index('input.value = ""') < body.index("await api(")
    assert "const body = { key: input.value }" in body
    assert "innerHTML" not in js and "textContent = " not in js
    assert "?key=" not in js and "location" not in js


def test_app_strips_the_token_from_the_url():
    js = text("app.js")
    assert 'sessionStorage.setItem("xc-token"' in js
    assert "history.replaceState" in js
    i = js.index("takeToken();")
    assert i < js.index("show((location.hash")           # before the first view reads the hash
    assert i < js.index("await bus.start()")


def test_token_goes_with_every_request():
    """D-039: api() sends X-Exo-Token on every call, and stream() puts it on the EventSource URL."""
    js = text("dom.js")
    api = js[js.index("export async function api("):js.index("await fetch(path")]
    assert '"X-Exo-Token": token()' in api and "startsWith(" not in api
    stream = js[js.index("export function stream("):js.index("export async function api(")]
    assert "new EventSource(" in stream and '"token="' in stream


@pytest.mark.skipif(not shutil.which("node"), reason="Node is needed to execute the browser save handler")
@pytest.mark.parametrize("source,warning,kind", [
    ("file", "", "ok"),
    ("keychain", "The keychain key still wins; the saved file key is shadowed. Update with --store keychain.", "bad"),
])
def test_web_save_handler_displays_effective_source_and_warning(source, warning, kind):
    script = r'''
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const func = src.slice(src.indexOf("async function save("), src.indexOf("async function test("));
const data = JSON.parse(fs.readFileSync(0, "utf8"));
const results = [], input = { value: "synthetic-browser-test-key" };
const context = { api: async () => data, show: (...args) => results.push(args), load: () => {}, alive: false };
vm.createContext(context);
vm.runInContext(func + "; this.save = save;", context);
context.save({provider: "openai"}, input).then(() => {
  process.stdout.write(JSON.stringify({results, input: input.value}));
}).catch(() => process.exit(1));
'''
    data = {"stored_in": "file", "effective_source": source, "shadowed_by_env": False,
            "warning": warning, "var": "OPENAI_API_KEY", "core_reloaded": True}
    proc = subprocess.run([shutil.which("node"), "-e", script, str(STATIC / "providers.js")],
                          input=json.dumps(data), capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    rendered = json.loads(proc.stdout)
    name, message, css = rendered["results"][0]
    assert name == "openai" and "Stored in file" in message and f"Effective source: {source}" in message
    assert warning in message and css == kind and rendered["input"] == ""
    assert "synthetic-browser-test-key" not in proc.stdout


@pytest.mark.skipif(not shutil.which("node"), reason="Node is needed to execute the browser status chip")
def test_web_chip_shows_a_provider_without_base_url_cannot_answer():
    """A key alone is not a route: the router gives a provider with no base_url no credential."""
    script = r'''
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const func = src.slice(src.indexOf("function chip("), src.indexOf("export function mount("));
const context = { pill: (text, cls) => [text, cls] };
vm.createContext(context);
vm.runInContext(func + "; this.chip = chip;", context);
const row = { status: "no base_url", needs: "key", key: "found", ready: false, verified: false };
process.stdout.write(JSON.stringify([context.chip(row), context.chip({ ...row, status: "key found", ready: true })]));
'''
    proc = subprocess.run([shutil.which("node"), "-e", script, str(STATIC / "providers.js")],
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [["no base_url", "off"], ["key found", "known"]]


NODE = shutil.which("node")


def run_node(script):
    proc = subprocess.run([NODE, "-e", script, str(STATIC / "providers.js")],
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.skipif(not NODE, reason="Node is needed to execute the model-list read")
def test_a_failed_model_read_keeps_the_last_good_list_and_names_its_kind():
    """D-091: the read never empties the picker on a failure, and a refused request is not offered a retry."""
    script = r'''
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const func = src.slice(src.indexOf("async function loadModels("), src.indexOf("async function load("));
const scope = `
let models = null, modelsError = null, alive = true, loadGeneration = 0, apiImpl = null;
async function api() { return apiImpl(); }
${func}
this.run = async (start, impl, generation) => {
  models = start; modelsError = null; loadGeneration = generation; apiImpl = impl;
  await loadModels(generation);
  return { models, modelsError };
};
this.supersede = (n) => { loadGeneration = n; };`;
const context = {};
vm.createContext(context);
vm.runInContext(scope, context);
const good = { models: [{ role: "main", route: "p:one" }], available: [] };
(async () => {
  const kept = await context.run(good, async () => {
    const e = new Error("The connection was lost."); e.name = "transport"; throw e;
  }, 1);
  const down = await context.run(good, async () => ({ models: [], available: [],
    error: "Exo core is not reachable.", error_class: "transport", retryable: true }), 2);
  const refused = await context.run(good, async () => ({ models: [], available: [],
    error: "Only the principal may list models.", error_class: "authority", retryable: false }), 3);
  const stale = await context.run(good, async () => {
    context.supersede(9);                                  // a newer read started while this one was waiting
    return { models: [], available: [], error: "late", error_class: "transport", retryable: true };
  }, 4);
  const first = await context.run(null, async () => ({ models: [{ role: "main", route: "p:two" }], available: [] }), 5);
  process.stdout.write(JSON.stringify({ kept, down, refused, stale, first, modelsAfter: context.run.length >= 0 }));
})().catch((e) => { process.stderr.write(String(e)); process.exit(1); });
'''
    out = run_node(script)
    assert out["kept"]["models"] == {"models": [{"role": "main", "route": "p:one"}], "available": []}
    assert out["kept"]["modelsError"] == {"text": "The connection was lost.", "cls": "other", "retryable": True}
    assert out["down"]["modelsError"] == {"text": "Exo core is not reachable.", "cls": "transport", "retryable": True}
    assert out["refused"]["modelsError"] == {"text": "Only the principal may list models.", "cls": "authority", "retryable": False}
    assert out["stale"]["models"] == {"models": [{"role": "main", "route": "p:one"}], "available": []}
    assert out["stale"]["modelsError"] is None, "a superseded read must not overwrite the newer one"
    assert out["first"]["models"] == {"models": [{"role": "main", "route": "p:two"}], "available": []}


@pytest.mark.skipif(not NODE, reason="Node is needed to execute the default-model picker")
def test_the_picker_offers_a_retry_only_where_retrying_can_help():
    """D-091: a refusal says to reopen the tab after the core restarts; a transport failure gets a button, and a
    kept list carries the reason above itself instead of replacing it."""
    script = r'''
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const func = src.slice(src.indexOf("function picker("), src.indexOf("function draw("));
const scope = `
function h(tag, props, ...kids) { return { tag, props, kids }; }
function createModelPicker(opts) { const el = { tag: "picker", opts, error: null };
  return { element: el, focus() {}, setRows() {}, setError: (t) => { el.error = t; } }; }
let results = {}, picked = "", models = null, modelsError = null;
function saveDefault() {} function retryModels() {}
${func}
this.run = (rows, err) => { models = rows; modelsError = err; return picker(); };`;
const context = {};
vm.createContext(context);
vm.runInContext(scope, context);
const rows = { models: [{ role: "main", route: "p:one" }], available: [] };
const pick = (rowsIn, err) => {
  const out = context.run(rowsIn, err);
  const [section, warn, retry] = [out, ...out.kids];
  const inner = out.kids[0];
  return { rows: inner.opts.rows, error: inner.error, warn: (out.kids[1] && out.kids[1].props && out.kids[1].props.class) || null,
    retry: out.kids.some((k) => k && k.tag === "div" && k.props && k.props.class === "xc-prov-def-act") };
};
process.stdout.write(JSON.stringify({
  transport: pick(null, { text: "The core is down.", cls: "transport", retryable: true }),
  authority: pick(null, { text: "Only the principal may do this.", cls: "authority", retryable: false }),
  kept: pick(rows, { text: "The core is down.", cls: "transport", retryable: true }),
  fine: pick(rows, null),
}));
'''
    out = run_node(script)
    assert out["transport"]["rows"] == [] and out["transport"]["error"] == "The core is down."
    assert out["transport"]["retry"] is True
    assert out["authority"]["rows"] == [] and out["authority"]["retry"] is False
    assert out["authority"]["error"] == "Only the principal may do this. Reopen this tab after the core restarts."
    assert out["kept"]["rows"] == [{"role": "main", "route": "p:one"}]
    assert out["kept"]["warn"] == "xc-warn" and out["kept"]["error"] is None
    assert out["fine"]["warn"] is None and out["fine"]["retry"] is False
    assert out["fine"]["rows"] == [{"role": "main", "route": "p:one"}]
