// Desktop interface preferences: the small set of UI choices needed to put the
// page back where the user left it. Conversations and memory stay in the core;
// this module never holds them, and it never holds the page access token.
//
// Two copies exist, by design. The browser copy lives in localStorage under
// KEY, so it only applies at the origin that wrote it (an origin includes its
// port). The desktop app also keeps a copy outside the browser, in its own
// preferences, and injects it as window.__exoDesktopPrefs before page scripts
// run. When the port changes, the browser copy is unreachable at the new
// origin, and the injected copy is what restores the thread, view and layout.
// The browser copy wins key by key when both exist, because it is the one the
// page itself just wrote.
//
// Only the allowlisted keys are ever read, written or posted to the app. A
// token, launch code, URL or fragment passed in here is dropped, not stored.
export const DESKTOP_STATE_KEY = "xc-desktop-state";
export const VIEWS = ["chat", "tasks", "schedule", "command", "providers"];
export const LAYOUTS = ["inverse", "classic"];

function isId(v) { return typeof v === "string" && v.length > 0 && v.length <= 200; }
function isFraction(v) { return typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1; }

// Keep exactly the restoration keys, and nothing else. Unknown keys, a token
// under any name, and a URL/fragment are all dropped.
export function cleanPrefs(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  if (VIEWS.includes(value.view)) out.view = value.view;
  if (isId(value.thread)) out.thread = value.thread;
  if (LAYOUTS.includes(value.layout)) out.layout = value.layout;
  if (isFraction(value.scroll)) out.scroll = value.scroll;
  return out;
}

// The browser store when one is available; null in a context without one (a test harness, private
// mode that throws on access). A missing store is not an error: the injected app copy still applies.
function storeOrNull(store) {
  try {
    if (store) return store;
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch (e) { return null; }
}

function readStore(store) {
  try {
    const s = storeOrNull(store);
    if (!s) return {};
    const raw = s.getItem(DESKTOP_STATE_KEY);
    if (!raw) return {};
    return cleanPrefs(JSON.parse(raw));
  } catch (e) { return {}; }
}

// The merged restoration state: the browser copy first, the app-injected copy
// filling any key the browser copy does not have. `injected` is
// window.__exoDesktopPrefs when the page runs inside the desktop app, and
// undefined in a plain browser, where the browser copy is the only source.
export function readState(store, injected) {
  const fromStore = readStore(store);
  const fromApp = cleanPrefs(injected);
  return { ...fromApp, ...fromStore };
}

// Save a patch: merge it into the stored copy, write only the allowlisted
// keys, and hand the same cleaned patch to `notify` (the desktop app's
// message handler) when one is supplied. Returns the cleaned patch that was
// stored, so a caller can check a token never survived.
export function writeState(store, patch, notify) {
  const cleaned = cleanPrefs(patch);
  const merged = { ...readStore(store), ...cleaned };
  try {
    const s = storeOrNull(store);
    if (s) s.setItem(DESKTOP_STATE_KEY, JSON.stringify(merged));
  } catch (e) { /* private mode: lasts this page only */ }
  if (typeof notify === "function") {
    try { notify(cleaned); } catch (e) { /* the app side is optional */ }
  }
  return cleaned;
}

// Post the cleaned patch to the desktop app, if the app exposed its handler.
// A plain browser has no handler and this is a no-op.
export function notifyApp(patch) {
  try {
    const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.exoDesktop;
    if (handler) handler.postMessage(cleanPrefs(patch));
  } catch (e) { /* no app handler: the browser copy is enough */ }
}

// Which thread to open at boot. A saved thread that is still listed opens.
// A saved thread that is gone returns null on purpose: the caller shows the
// thread picker instead of silently opening a different thread. With no saved
// thread, the first listed thread opens, as before.
export function pickThread(savedThread, sessions) {
  const list = Array.isArray(sessions) ? sessions : [];
  if (savedThread) return list.some((s) => s && s.id === savedThread) ? savedThread : null;
  return list.length ? list[0].id : null;
}

// Scroll position as a fraction of the scrollable range, so it survives a
// transcript that grew or shrank since it was saved. 0 is the top.
export function scrollFraction(scrollTop, scrollHeight, clientHeight) {
  const range = scrollHeight - clientHeight;
  if (!(range > 0)) return 0;
  return Math.min(1, Math.max(0, scrollTop / range));
}

export function scrollTopFor(fraction, scrollHeight, clientHeight) {
  const range = scrollHeight - clientHeight;
  if (!(range > 0)) return 0;
  return Math.min(range, Math.max(0, fraction * range));
}
