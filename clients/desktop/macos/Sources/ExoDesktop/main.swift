import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var launcher = ExoWebLauncher()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "Exo"
        window.makeKeyAndOrderFront(nil)
        self.window = window

        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: window.contentView?.bounds ?? .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.autoresizingMask = [.width, .height]
        window.contentView?.addSubview(webView)
        self.webView = webView

        buildMenu()
        launcher.start { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let url):
                    webView.load(URLRequest(url: url))
                case .failure(let error):
                    let alert = NSAlert()
                    alert.messageText = "Exo did not start"
                    alert.informativeText = error.description + "\nRun `exo web` in a terminal for the full message."
                    alert.addButton(withTitle: "Quit")
                    alert.runModal()
                    NSApp.terminate(nil)
                }
            }
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        // Stops the web server first, then allows termination. The core
        // keeps running, as with `exo web`.
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
        if isLoopback(url) {
            decisionHandler(.allow)
            return
        }
        decisionHandler(.cancel)
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        components?.fragment = nil
        if let external = components?.url {
            NSWorkspace.shared.open(external)
        }
    }

    private func isLoopback(_ url: URL) -> Bool {
        guard url.scheme == "http" else { return false }
        return url.host == "127.0.0.1" || url.host == "localhost" || url.host == "::1"
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
        exoMenu.addItem(NSMenuItem(title: "Stop Core", action: #selector(stopCore), keyEquivalent: ""))
        exoMenuItem.submenu = exoMenu
        mainMenu.addItem(exoMenuItem)
        NSApp.mainMenu = mainMenu
    }

    @objc private func reloadPage() {
        webView?.reload()
    }

    @objc private func stopCore() {
        launcher.stopCore { code in
            DispatchQueue.main.async {
                let alert = NSAlert()
                if code == 0 {
                    alert.messageText = "Core stopped"
                    alert.informativeText = "The background core is stopped. Reload the page to start it again."
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

let delegate = AppDelegate()
NSApplication.shared.delegate = delegate
NSApplication.shared.run()
