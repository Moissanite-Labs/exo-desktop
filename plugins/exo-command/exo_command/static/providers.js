// Providers view: where model keys go, per-provider status, key save/test/remove, and the default model.
// Drawn as an instrument panel (D-061): one ruled row per provider, status in a pill whose led form carries it.
// A key value only ever lives in the password field. It is read once to build the request body, the field is
// cleared at once (also on error), and it is never logged, stored, put in a URL, or shown again.
import { h, api, errorBox, pageHead, readout, pill, emptyState } from "./dom.js";

import { createModelPicker } from "./model_picker.js";

const STORE_TEXT = {
  keychain: "the macOS Keychain",
  "secret-service": "the system keyring (Secret Service)",
  file: "a private keys file in your Exo home (mode 600)",
};

function chip(r) {
  const st = r.status || "";
  const lt = r.last_test || {};
  if (r.verified) return pill("verified" + (lt.latency_ms != null ? " · " + Math.round(lt.latency_ms) + " ms" : ""), "ok");
  if (st.startsWith("failed")) return pill(st, "fail");
  if (st === "no base_url") return pill(st, "off");  // nothing to call: the router skips it even with a key
  if (st === "configured") return pill("configured · untested", "known");
  if (r.needs === "key") return pill(r.key === "found" ? "key found" : "no key", r.key === "found" ? "known" : "off");
  if (r.needs === "cli") return pill(r.ready ? "cli installed" : "cli not installed", r.ready ? "known" : "off");
  return pill(r.local ? (r.reachable ? "local · running" : "local · not running") : st, r.reachable ? "ok" : "off");
}

export function mount(root) {
  const body = h("div", { class: "xc-prov" });
  const counts = h("div", { class: "xc-phead-read" });
  root.replaceChildren(h("div", { class: "xc-pg" }, pageHead({ eyebrow: "05 / Providers", title: "Providers",
    lede: "Where model keys live, which providers answer, and the model the main role uses.", aside: counts }), body));
  let alive = true;

  if (!sessionStorage.getItem("xc-token")) {
    body.replaceChildren(emptyState({ k: "Page token missing", title: "Open the link exo web printed.",
      body: "It carries a page token that this page needs to set up providers. The bare address has none." }));
    return () => { alive = false; };
  }

  const results = {};   // provider name -> {text, cls}; kept across redraws, never holds a key
  let data = null, models = null, modelsError = null, modelsLoading = false, err = "", picked = "", savingDefault = false;
  let loadGeneration = 0, modelsGeneration = 0;
  let custom = [], customError = "", editing = null;
  let layout = null, pickerLoading = false;
  // The model search a retry moved focus to. The person has not used it yet, so it does not hold back a redraw, and
  // the redraw moves focus to the new search. It is the person's once they type in it, press a key in it or click it,
  // or once focus leaves it for another part of the page. Back in it by Tab or its label, it then holds the panel.
  let placedSearch = null;
  function place(search) {
    placedSearch = search;
    const used = () => { if (placedSearch === search) placedSearch = null; };
    for (const kind of ["keydown", "input", "pointerdown"]) search.addEventListener(kind, used, { once: true });
    // A switch to another window or tab also blurs it, but the page then has no focus, and focus comes back to the
    // search unused. Not once: the first blur may be such a switch.
    search.addEventListener("blur", () => { if (document.hasFocus()) used(); });
  }

  // D-091: a failed model list says which failure it was. A transport failure can be retried; an authority
  // refusal cannot, so it gets no button. A failed retry keeps the last good list, so the picker stays usable.
  // Each read takes a generation; only the newest one may change the list, so a slow read never overwrites a newer one.
  // Says whether this read was the newest, so its reply was applied.
  async function loadModels() {
    const generation = ++modelsGeneration;
    let next = null, failure = null;
    try {
      const d = await api("GET", "/api/providers/models");
      if (d && d.error) failure = { text: d.error, cls: d.error_class || "other", retryable: d.retryable !== false };
      else next = d;
    } catch (e) {
      failure = { text: e.message || "The model list could not be read.", cls: "other", retryable: true };
    }
    if (!alive || generation !== modelsGeneration) return false;
    modelsLoading = false;
    if (failure) modelsError = failure;
    else { models = next; modelsError = null; }
    return true;
  }

  async function load() {
    const generation = ++loadGeneration;
    try {
      const next = await api("GET", "/api/providers");
      let nextCustom = null, nextCustomError = "";
      try { nextCustom = (await api("GET", "/api/providers/custom")).providers || []; }
      catch (e) { nextCustomError = "Custom provider settings are unavailable. Connect to the core and try again."; }
      await loadModels();
      if (!alive || generation !== loadGeneration) return;
      data = next; err = "";
      if (nextCustom) custom = nextCustom;
      customError = nextCustomError;
    } catch (e) { if (generation === loadGeneration) err = e.message; }
    if (alive && generation === loadGeneration) draw();
  }

  // Names a control in the panel by its provider row or section, its tag and its label. A redraw replaces the
  // controls it draws, so this is how the new copy of the one that held focus is found. Empty for anything else.
  function controlKey(el) {
    if (!el || el === body || !body.contains(el)) return "";
    const row = el.closest(".xc-prow");
    const place = row ? row.querySelector(".xc-prow-name").textContent : (el.closest("section") || body).getAttribute("aria-label");
    return [place, el.tagName, el.getAttribute("aria-label") || el.textContent].join("\n");
  }

  // A retry redraws the section, which drops the focused Try again button. If focus is still lost after the
  // reply, it goes back to the panel control the person moved to while the retry ran (#1014). Else it goes to
  // Try again when that is drawn again, else to the model search, which the picker draws even with no list. The
  // warning note (as exo's refusal message) and then the workspace stay as fallbacks if neither is drawn.
  // A load started meanwhile (a Test, a Save) supersedes the retry, and so does a newer read of the list. That load
  // draws its own reply, so a superseded retry neither draws nor moves focus (D-091, fork amendment of 2026-11-01).
  // A model search this puts focus on is placed (see place()), so it does not hold back a later load's draw.
  async function retryModels() {
    if (!alive || modelsLoading) return;
    const generation = loadGeneration;
    modelsLoading = true; modelsError = null;
    draw();
    const newest = await loadModels();
    if (!alive || !newest || generation !== loadGeneration) return;
    const moved = controlKey(document.activeElement);
    draw();
    if (document.activeElement !== document.body) return;
    const same = moved && [...body.querySelectorAll("a[href], button, input, select, textarea, [tabindex]")].find((el) => controlKey(el) === moved);
    const again = [...body.querySelectorAll(".xc-prov-def button")].find((b) => b.textContent === "Try again");
    const note = body.querySelector(".xc-prov-def .xc-warn");
    const next = same || again || body.querySelector(".xc-prov-def .xc-model-search") || note || root;
    if (next === note) note.tabIndex = -1;
    if (next.classList.contains("xc-model-search")) place(next);
    next.focus();
  }

  function show(name, text, cls) { results[name] = { text, cls }; if (alive) draw(); }

  async function save(r, input) {
    const body = { key: input.value };
    input.value = "";                                   // cleared before the request, so it is gone on any outcome
    if (!body.key.trim()) { show(r.provider, "Paste a key first.", "bad"); return; }
    try {
      const d = await api("POST", "/api/providers/" + encodeURIComponent(r.provider) + "/key", body);
      const warning = d.warning || (d.shadowed_by_env ? "The env var " + d.var + " shadows it." : "");
      show(r.provider, "Stored in " + d.stored_in + ". Effective source: " + (d.effective_source || "not confirmed") + "." +
        (warning ? " " + warning : "") +
        (d.core_reloaded ? "" : " The core was not told to reload; restart it to refresh credentials."), warning ? "bad" : "ok");
    } catch (e) { show(r.provider, e.message, "bad"); }
    body.key = "";
    if (alive) load();
  }

  async function test(r) {
    show(r.provider, "Testing...", "");
    try {
      const d = await api("POST", "/api/providers/" + encodeURIComponent(r.provider) + "/test", {});
      show(r.provider, d.ok ? "Test ok in " + Math.round(d.latency_ms || 0) + " ms." : "Test failed: " + (d.error_class || "error") + (d.detail ? " " + d.detail : ""), d.ok ? "ok" : "bad");
    } catch (e) { show(r.provider, e.message, "bad"); }
    if (alive) load();
  }

  async function remove(r) {
    if (!confirm("Remove the stored key for " + r.provider + "?")) return;
    try {
      const d = await api("POST", "/api/providers/" + encodeURIComponent(r.provider) + "/remove", {});
      show(r.provider, "Removed from " + ((d.removed_from || []).join(", ") || "nothing") + "." + ((d.still_in_env || []).length ? " Still set in the environment: " + d.still_in_env.join(", ") + "." : ""), "ok");
    } catch (e) { show(r.provider, e.message, "bad"); }
    if (alive) load();
  }

  function row(r) {
    const meta = [];   // [label, value]
    if (r.needs === "key") meta.push(["key", r.key === "found" ? "from " + (r.source || "?") : "missing"]);
    if (r.key_env && r.key_env.length) meta.push(["env", r.key_env.join(" / ")]);
    meta.push(["models", r.models != null ? String(r.models) : "n/a"]);
    if (r.serves && r.serves.length) meta.push(["serves", r.serves.join(", ")]);
    const kids = [h("div", { class: "xc-prow-top" },
      h("div", { class: "xc-prow-id" }, h("span", { class: "xc-prow-name" }, r.provider === "gemini" ? "Google Gemini (AI Studio)" : r.provider), r.default ? h("span", { class: "xc-defmark" }, "default") : null),
      h("div", { class: "xc-prow-st" }, chip(r)),
      h("dl", { class: "xc-prow-meta" }, meta.map((m) => h("div", null, h("dt", null, m[0]), h("dd", null, m[1])))))];
    if (r.needs === "key") {
      const input = h("input", { class: "xc-field", type: "password", autocomplete: "new-password", spellcheck: "false",
        autocapitalize: "off", placeholder: r.key === "found" ? "replace the key" : "paste the key", "aria-label": "API key for " + r.provider });
      const form = h("form", { class: "xc-prow-act", onsubmit: (e) => { e.preventDefault(); save(r, input); } }, input,
        h("button", { class: "xc-btn", type: "submit" }, "Save"),
        h("button", { class: "xc-btn", type: "button", onclick: () => test(r) }, "Test"),
        h("button", { class: "xc-btn", type: "button", onclick: () => remove(r) }, "Remove"));
      kids.push(form);
    } else {
      kids.push(h("div", { class: "xc-prow-act" }, h("button", { class: "xc-btn", type: "button", onclick: () => test(r) }, "Test")));
    }
    if (r.provider === "gemini") kids.push(h("p", { class: "xc-prov-res" },
      "Google AI Studio key; uses Google's OpenAI-compatible Chat Completions API, not Vertex AI or the native Gemini API. Restart an older core to use this preset."));
    const res = results[r.provider];
    if (res) kids.push(h("div", { class: "xc-prov-res " + (res.cls || ""), role: "status" }, res.text));
    return h("div", { class: "xc-prow" + (r.default ? " def" : ""), role: "listitem" }, kids);
  }

  function customPanel() {
    const summary = results._custom;
    const section = h("section", { class: "xc-custom", "aria-label": "Custom providers" },
      h("h2", null, "Custom providers"),
      h("p", null, "Configure an OpenAI Chat Completions or Anthropic Messages endpoint. Other protocols are not supported here. Changes take effect after the core restarts."),
      h("p", null, "For OpenAI-compatible servers include the API base path (such as /v1). For Anthropic Messages use the service root; Exo adds /v1/messages."),
      h("p", null, "Use HTTPS for remote services: HTTP sends API keys without encryption. Changing the endpoint or protocol uses a different stored key."),
      h("p", null, "Keys are stored on the web server's machine. A core on another machine needs its own credential. Seat-specific provider overrides can take precedence."));
    if (customError) section.appendChild(h("div", { class: "xc-warn", role: "status" }, customError));
    if (summary) section.appendChild(h("div", { class: "xc-prov-res " + summary.cls, role: "status" }, summary.text));
    for (const p of custom) section.appendChild(h("div", { class: "xc-custom-entry" },
      h("span", null, p.name + " · " + p.protocol + " · " + p.model),
      h("button", { class: "xc-btn", type: "button", onclick: () => { editing = { ...p, existing: true }; draw(true); } }, "Edit " + p.name)));
    if (!editing) {
      section.appendChild(h("button", { class: "xc-btn", type: "button", disabled: !!customError,
        onclick: () => { editing = { name: "", endpoint: "", protocol: "openai", auth: "key", model: "" }; draw(true); } }, "Add custom provider"));
      return section;
    }
    // Read once: a save clears `editing` before the form is replaced, so the form keeps its own entry's kind.
    const existing = !!editing.existing;
    const name = h("input", { class: "xc-field", value: editing.name, required: true, disabled: existing, "aria-label": "Provider name" });
    const endpoint = h("input", { class: "xc-field", value: editing.endpoint, type: "url", required: true, "aria-label": "Base URL" });
    const model = h("input", { class: "xc-field", value: editing.model, required: true, "aria-label": "Model ID" });
    const protocol = h("select", { class: "xc-field", "aria-label": "Protocol" },
      h("option", { value: "openai", selected: editing.protocol === "openai" }, "OpenAI Chat Completions (Bearer key)"),
      h("option", { value: "anthropic", selected: editing.protocol === "anthropic" }, "Anthropic Messages (x-api-key)"));
    const auth = h("select", { class: "xc-field", "aria-label": "Authentication" },
      h("option", { value: "key", selected: editing.auth === "key" }, "API key"),
      h("option", { value: "none", selected: editing.auth === "none" }, "No API key"));
    const key = h("input", { class: "xc-field", type: "password", autocomplete: "new-password", spellcheck: "false",
      autocapitalize: "off", "aria-label": "Custom provider API key", placeholder: "Optional; leave blank to keep the current endpoint's key" });
    const message = h("div", { class: "xc-prov-res bad", role: "status" });
    const saveButton = h("button", { class: "xc-btn xc-primary", type: "submit" }, "Save provider");
    const cancelButton = h("button", { class: "xc-btn", type: "button", onclick: () => { key.value = ""; editing = null; draw(true); } }, "Cancel");
    const field = (label, input) => h("label", null, h("span", null, label), input);
    const form = h("form", { class: "xc-custom-form", onsubmit: async (e) => {
      e.preventDefault();
      const request = { name: name.value, endpoint: endpoint.value, protocol: protocol.value, auth: auth.value, model: model.value, key: key.value, replace: existing };
      key.value = "";
      saveButton.disabled = cancelButton.disabled = true;
      try {
        const d = await api("POST", "/api/providers/custom", request);
        editing = null;
        results._custom = { text: "Saved " + d.provider + ". Restart the core to use these settings." + (d.warning ? " " + d.warning : ""), cls: d.warning ? "bad" : "ok" };
        await load();
      } catch (error) { message.replaceChildren(error.message || "Could not save provider."); }
      finally { request.key = ""; saveButton.disabled = cancelButton.disabled = false; }
    } }, field("Name", name), field("Base URL", endpoint), field("Protocol", protocol), field("Authentication", auth),
      field("Model ID", model), field("API key", key), message, h("div", { class: "xc-btnrow" }, saveButton, cancelButton));
    section.appendChild(form);
    return section;
  }

  async function saveDefault(ref) {
    if (!alive || savingDefault) return;
    savingDefault = true;
    try {
      const d = await api("POST", "/api/providers/default", { ref, role: "main" });
      if (!alive) return;
      picked = ref;
      results._default = { text: "Default set to " + ref + ((d.applied === true || d.applied === "now") ? "." : ". Saved; the core will use it on next start."), cls: "ok" };
    } catch (e) { if (alive) throw e; }
    finally { savingDefault = false; }
    // Let the picker finish and restore focus before a background refresh.
    setTimeout(() => { if (alive) load(); }, 0);
    return results._default && results._default.text;
  }

  // `carry` is the text typed into the search of the loading picker this one replaces. It goes in before a failure
  // is set, because typing in the search clears the picker's error.
  function picker(carry = "") {
    const rows = [...((models && models.models) || []), ...((models && models.available) || [])];
    // D-091: with no good list the picker says why it failed; with one it stays usable and is marked as the last good read.
    const failed = !!modelsError && !rows.length;
    const chosen = createModelPicker({ label: "Default model", rows: modelsLoading ? null : rows, selected: picked,
      applyLabel: "Save default", note: "The route the main role calls first.", onApply: saveDefault });
    if (carry) {
      const search = chosen.element.querySelector(".xc-model-search");
      search.value = carry;
      search.dispatchEvent(new Event("input"));
    }
    if (failed) chosen.setError(modelsError.text);
    pickerLoading = modelsLoading;
    const res = results._default;
    // Retryable failures keep Try again beside the last good list too.
    return h("section", { class: "xc-prov-def", "aria-label": "Default model" }, chosen.element,
      modelsError && !failed ? h("div", { class: "xc-warn", role: "status" }, modelsError.text + " This list is from the last good read.") : null,
      modelsError && modelsError.retryable ? h("div", { class: "xc-btnrow" },
        h("button", { class: "xc-btn", type: "button", onclick: retryModels }, "Try again")) : null,
      res ? h("div", { class: "xc-prov-res " + (res.cls || ""), role: "status" }, res.text) : null);
  }

  function draw(force = false) {
    if (err) {
      if (editing && layout) layout.before.replaceChildren(errorBox(err));
      else { layout = null; body.replaceChildren(errorBox(err)); }
      return;
    }
    if (!data) { layout = null; body.replaceChildren(h("div", { class: "xc-loading" }, "Loading providers...")); return; }
    const rows = data.providers || [];
    const active = document.activeElement;
    const keep = active && active.tagName === "INPUT" && ((active.type === "password" && active.value) || active.classList.contains("xc-model-search")) ? active : null;
    // Never redraw while a key is being typed or a model searched. The layout keeps the custom form, so a key in it
    // does not stop a redraw. Nor does a search in a picker drawn while loading, so a retry's reply is drawn, or a
    // search the retry placed focus on and the person has not used.
    const search = keep && keep.classList.contains("xc-model-search") &&
      ((pickerLoading && !modelsLoading) || keep === placedSearch) ? keep : null;
    if (keep && !search && !(active.closest && active.closest(".xc-custom-form"))) {
      // The rest waits, but the custom providers section, which never holds that field, still follows a save, Add,
      // Edit or Cancel. Left as it was, a form whose save cleared `editing` stayed open with nothing to edit.
      if (layout && (force || !editing)) layout.custom.replaceChildren(customPanel());
      return;
    }
    const ready = rows.filter((r) => r.verified || r.ready).length;
    const def = rows.find((r) => r.default);
    counts.replaceChildren(readout([["Ready", ready + " / " + rows.length, ready ? "ok" : "off"],
      ["Default", def ? def.provider : "not set", def ? "on" : "off"]]));
    if (!layout) {
      layout = { before: h("div", { class: "xc-prov-slot" }), custom: h("div", { class: "xc-prov-slot" }),
        after: h("div", { class: "xc-prov-slot" }) };
      body.replaceChildren(layout.before, layout.custom, layout.after);
      force = true;
    }
    layout.before.replaceChildren(...[
      h("p", { class: "xc-prov-lead" }, h("span", { class: "xc-led", "data-s": "known", "aria-hidden": "true" }),
        "Keys are stored in " + (STORE_TEXT[data.store] || data.store || "the local store") +
        ". They are sent to this local server once, never shown again, and never kept in the browser."),
      data.ready || !rows.length ? null : h("div", { class: "xc-warn" }, "No model provider is ready yet. Add a key below."),
      rows.length ? h("div", { class: "xc-prov-list", role: "list" }, rows.map(row)) : emptyState({ k: "No providers",
        title: "This core knows no model provider yet.",
        body: "Providers come from the core's router config: hosted APIs that need a key, command-line tools, and local servers.",
        hint: "Add one to the config or start a local server such as Ollama, then open this tab again." })].filter(Boolean));
    // Keep the actual form node (including focus and password input) during unrelated refreshes.
    if (force || !editing) layout.custom.replaceChildren(customPanel());
    // Read before the old search is removed. Chrome fires blur on a focused field it removes, which would make it the
    // person's.
    const placed = !!search && search === placedSearch;
    const pick = picker(search ? search.value : "");
    layout.after.replaceChildren(...(pick ? [pick] : []));
    // The new picker's search takes the focus of the search it replaced, and stays placed if that one was.
    // picker() carried its text.
    const next = search && layout.after.querySelector(".xc-model-search");
    if (next) { if (placed) place(next); next.focus(); }
  }

  draw();
  load();
  return () => { alive = false; };
}
