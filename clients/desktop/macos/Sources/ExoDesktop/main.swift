import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var origin: URL?
    private var launcher = ExoWebLauncher()
    private var isAttached: Bool { Bundle.main.object(forInfoDictionaryKey: "ExoAttachedCore") as? Bool == true }
    private var transitioning = false
    private var terminating = false
    private var showingFailure = false
    // Interface state only: the view, thread, layout and transcript position the page needs to restore itself.
    // The page access token is never stored here, never injected, and never logged. Conversations and memory
    // stay in the core; this is only the pointer back to where the user was.
    private let frameAutosaveName = "ExoDesktopMain"
    private let prefsKey = "ExoDesktopUIPrefs"
    private let prefViews = ["chat", "tasks", "schedule", "command", "providers"]
    private let prefLayouts = ["inverse", "classic"]

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String ?? "Exo"
        window.delegate = self
        window.setFrameAutosaveName(frameAutosaveName)
        let hadSavedFrame = UserDefaults.standard.string(forKey: "NSWindow Frame \(frameAutosaveName)") != nil
        window.setFrameUsingName(frameAutosaveName)
        if !hadSavedFrame || !NSScreen.screens.contains(where: { window.frame.intersects($0.visibleFrame) }) {
            window.center()
        }
        window.makeKeyAndOrderFront(nil)
        self.window = window

        let configuration = WKWebViewConfiguration()
        // Persistent, app-private store: the page's own saved choices (layout, and the desktop-state copy
        // in localStorage) survive quit/reopen. The page token is sessionStorage, which a new web view does
        // not carry over; each launch gets a fresh token in the page URL fragment, in memory only.
        // Persistence alone is not enough: browser storage belongs to an origin, and an origin includes
        // its port, so the launcher also pins the loopback port (see ExoWebLauncher) and the app keeps a
        // port-independent copy of the same preferences below, injected before page scripts run.
        configuration.websiteDataStore = .default()
        let contentController = WKUserContentController()
        contentController.add(self, name: "exoDesktop")
        contentController.addUserScript(WKUserScript(source: desktopPrefsScript(), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        configuration.userContentController = contentController
        let webView = WKWebView(frame: window.contentView?.bounds ?? .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        window.contentView?.addSubview(webView)
        self.webView = webView

        buildMenu()
        NSApp.activate(ignoringOtherApps: true)
        startServer()
    }

    // The port-independent copy of the page's restoration preferences, as a script the page reads as
    // window.__exoDesktopPrefs before its own scripts run. Only the allowlisted keys are injected, and
    // the value is built from the stored dictionary, so a token could not reach the page this way even
    // if one were posted: the message handler below refuses to store anything but the allowlist.
    private func desktopPrefsScript() -> String {
        let stored = UserDefaults.standard.dictionary(forKey: prefsKey) ?? [:]
        let cleaned = cleanPrefs(stored)
        guard let data = try? JSONSerialization.data(withJSONObject: cleaned, options: []),
              let json = String(data: data, encoding: .utf8) else {
            return "window.__exoDesktopPrefs = {};"
        }
        return "window.__exoDesktopPrefs = \(json);"
    }

    private func cleanPrefs(_ value: [String: Any]) -> [String: Any] {
        var out: [String: Any] = [:]
        if let view = value["view"] as? String, prefViews.contains(view) { out["view"] = view }
        if let thread = value["thread"] as? String, !thread.isEmpty, thread.count <= 200 { out["thread"] = thread }
        if let layout = value["layout"] as? String, prefLayouts.contains(layout) { out["layout"] = layout }
        if let scroll = value["scroll"] as? Double, scroll >= 0, scroll <= 1 { out["scroll"] = scroll }
        return out
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "exoDesktop", let body = message.body as? [String: Any] else { return }
        var stored = UserDefaults.standard.dictionary(forKey: prefsKey) ?? [:]
        for (key, value) in cleanPrefs(body) { stored[key] = value }
        UserDefaults.standard.set(stored, forKey: prefsKey)
    }

    func windowDidMove(_ notification: Notification) {
        window?.saveFrame(usingName: frameAutosaveName)
    }

    func windowDidResize(_ notification: Notification) {
        window?.saveFrame(usingName: frameAutosaveName)
    }

    private func startServer() {
        guard !terminating, let webView else { return }
        transitioning = true
        let currentLauncher = launcher
        webView.loadHTMLString("<html><body style=\"font:20px -apple-system;padding:48px\">Starting Exo…</body></html>", baseURL: nil)
        launcher.onExit = { [weak self, weak currentLauncher] _ in
            DispatchQueue.main.async {
                guard let self, let currentLauncher, self.launcher === currentLauncher, !self.transitioning, !self.terminating else { return }
                self.showFailure("The Exo web server stopped.")
            }
        }
        launcher.start { result in
            DispatchQueue.main.async {
                guard !self.terminating, self.launcher === currentLauncher else { return }
                self.transitioning = false
                switch result {
                case .success(let url):
                    self.origin = url
                    webView.load(URLRequest(url: url))
                case .failure(let error):
                    self.showFailure(error.description)
                }
            }
        }
    }

    private func showFailure(_ message: String) {
        guard !terminating, !transitioning, !showingFailure else { return }
        showingFailure = true
        let alert = NSAlert()
        alert.messageText = "Exo is unavailable"
        alert.informativeText = message
        alert.addButton(withTitle: "Retry")
        alert.addButton(withTitle: "Quit")
        if alert.runModal() == .alertFirstButtonReturn {
            showingFailure = false
            reloadPage()
        } else {
            showingFailure = false
            NSApp.terminate(nil)
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        // Stops the web server first, then allows termination. The core
        // keeps running, as with `exo web`.
        window?.saveFrame(usingName: frameAutosaveName)
        terminating = true
        transitioning = true
        launcher.onExit = nil
        launcher.stopWebServer {
            DispatchQueue.main.async {
                NSApp.reply(toApplicationShouldTerminate: true)
            }
        }
        return .terminateLater
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        // Closing the window quits the app. Without this, the app would keep
        // running with no visible window and no way to reopen it.
        return true
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.scheme == "about" || (url.scheme == origin?.scheme && url.host == origin?.host && url.port == origin?.port) {
            decisionHandler(.allow)
            return
        }
        decisionHandler(.cancel)
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        components?.fragment = nil
        if ["http", "https"].contains(url.scheme ?? ""), let external = components?.url {
            NSWorkspace.shared.open(external)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if navigationAction.targetFrame == nil { webView.load(navigationAction.request) }
        return nil
    }

    private func buildMenu() {
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(title: "Quit Exo", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        let exoMenuItem = NSMenuItem()
        let exoMenu = NSMenu(title: "Exo")
        exoMenu.addItem(NSMenuItem(title: "Reload Page", action: #selector(reloadPage), keyEquivalent: "r"))
        if !isAttached {
            exoMenu.addItem(NSMenuItem(title: "Stop Core", action: #selector(stopCore), keyEquivalent: ""))
        }
        exoMenuItem.submenu = exoMenu
        mainMenu.addItem(exoMenuItem)
        let editItem = NSMenuItem()
        let edit = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            edit.addItem(NSMenuItem(title: title, action: Selector(action), keyEquivalent: key))
        }
        editItem.submenu = edit
        mainMenu.addItem(editItem)
        NSApp.mainMenu = mainMenu
    }

    @objc private func reloadPage() {
        guard !terminating, !transitioning, !showingFailure else { return }
        transitioning = true
        launcher.stopWebServer { DispatchQueue.main.async {
            guard !self.terminating else { return }
            self.launcher = ExoWebLauncher()
            self.startServer()
        } }
    }

    @objc private func stopCore() {
        guard !isAttached else { return }
        guard !terminating, !transitioning, !showingFailure else { return }
        transitioning = true
        let currentLauncher = launcher
        currentLauncher.stopWebServer {
          currentLauncher.stopCore { code in
            DispatchQueue.main.async {
                guard !self.terminating else { return }
                self.transitioning = false
                let alert = NSAlert()
                if code == 0 {
                    alert.messageText = "Core stopped"
                    alert.informativeText = "The background core and web server are stopped. Choose Reload Page to start again."
                } else {
                    alert.messageText = "Core stop failed"
                    alert.informativeText = "Run `exo stop` in a terminal for the full message."
                }
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
        }
    }
}

let delegate = AppDelegate()
NSApplication.shared.delegate = delegate
NSApplication.shared.run()
