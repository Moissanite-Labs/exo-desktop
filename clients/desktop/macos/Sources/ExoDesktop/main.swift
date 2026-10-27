import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var origin: URL?
    private var launcher = ExoWebLauncher()
    private var isAttached: Bool { Bundle.main.object(forInfoDictionaryKey: "ExoAttachedCore") as? Bool == true }
    private var transitioning = false
    private var terminating = false
    private var showingFailure = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String ?? "Exo"
        window.makeKeyAndOrderFront(nil)
        self.window = window

        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
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
