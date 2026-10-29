import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, NSTextFieldDelegate, WKScriptMessageHandler {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var findBar: NSView?
    private var findField: NSTextField?
    private var findPreviousButton: NSButton?
    private var findNextButton: NSButton?
    private var findDoneButton: NSButton?
    private var findResultLabel: NSTextField?
    private var statusBar: NSView?
    private var statusLabel: NSTextField?
    private var statusSpinner: NSProgressIndicator?
    private var origin: URL?
    private var launcher = ExoWebLauncher()
    private var isAttached: Bool { Bundle.main.object(forInfoDictionaryKey: "ExoAttachedCore") as? Bool == true }
    private var transitioning = false
    private var terminating = false
    private var showingFailure = false
    private var hasReachedReady = false
    private let desktopPreferences: DesktopPreferences?
    private static func configuredPreferences() -> DesktopPreferences? {
        let environment = ProcessInfo.processInfo.environment
        // A runtime override has no installer-verified core identity. Do not restore another core's pointer.
        guard (environment["EXO_DESKTOP_EXO"] ?? "").isEmpty else { return nil }
        if Bundle.main.object(forInfoDictionaryKey: "ExoAttachedCore") as? Bool != true,
           !(environment["EXO_SEAT"] ?? "").isEmpty { return nil }
        guard let scope = Bundle.main.object(forInfoDictionaryKey: "ExoPreferenceScope") as? String,
              scope.count == 64, scope.allSatisfy({ $0.isHexDigit }) else { return nil }
        return DesktopPreferences(scope: scope)
    }
    override convenience init() { self.init(preferences: Self.configuredPreferences()) }
    init(preferences: DesktopPreferences?) {
        self.desktopPreferences = preferences
        super.init()
    }
    private let frameAutosaveName = "ExoDesktopMain"
    private var pageGeneration = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        let restored = window.setFrameUsingName(frameAutosaveName)
        window.setFrameAutosaveName(frameAutosaveName)
        if !restored || !NSScreen.screens.contains(where: { window.frame.intersects($0.visibleFrame) }) { window.center() }
        window.title = Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String ?? "Exo"
        window.delegate = self
        window.makeKeyAndOrderFront(nil)
        self.window = window

        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        if desktopPreferences != nil { configuration.userContentController.add(self, name: "exoDesktop") }
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = []
        window.contentView?.addSubview(webView)
        self.webView = webView

        let statusBar = NSView(frame: .zero)
        statusBar.autoresizingMask = []
        let statusSpinner = NSProgressIndicator(frame: .zero)
        statusSpinner.style = .spinning
        statusSpinner.controlSize = .small
        statusSpinner.isDisplayedWhenStopped = false
        statusBar.addSubview(statusSpinner)
        let statusLabel = NSTextField(labelWithString: "")
        statusLabel.autoresizingMask = []
        statusBar.addSubview(statusLabel)
        window.contentView?.addSubview(statusBar)
        self.statusBar = statusBar
        self.statusSpinner = statusSpinner
        self.statusLabel = statusLabel

        let findBar = NSView(frame: .zero)
        findBar.autoresizingMask = []
        findBar.isHidden = true
        let findField = NSTextField(frame: .zero)
        findField.placeholderString = "Find in page"
        // Enter and Escape go through the delegate's doCommandBy below, not
        // through a control action: both firing would advance two matches.
        findField.delegate = self
        findBar.addSubview(findField)
        let findPreviousButton = NSButton(title: "Previous", target: self, action: #selector(findPrevious))
        findPreviousButton.bezelStyle = .rounded
        findBar.addSubview(findPreviousButton)
        let findNextButton = NSButton(title: "Next", target: self, action: #selector(findNext))
        findNextButton.bezelStyle = .rounded
        findBar.addSubview(findNextButton)
        let findDoneButton = NSButton(title: "Done", target: self, action: #selector(hideFindBar))
        findDoneButton.bezelStyle = .rounded
        findBar.addSubview(findDoneButton)
        let findResultLabel = NSTextField(labelWithString: "")
        findBar.addSubview(findResultLabel)
        window.contentView?.addSubview(findBar)
        self.findBar = findBar
        self.findField = findField
        self.findPreviousButton = findPreviousButton
        self.findNextButton = findNextButton
        self.findDoneButton = findDoneButton
        self.findResultLabel = findResultLabel

        buildMenu()
        layoutViews()
        NSApp.activate(ignoringOtherApps: true)
        startServer()
    }

    func windowDidResize(_ notification: Notification) {
        layoutViews()
        window?.saveFrame(usingName: frameAutosaveName)
    }

    func windowDidMove(_ notification: Notification) { window?.saveFrame(usingName: frameAutosaveName) }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard !transitioning, !terminating, message.webView === webView, message.name == "exoDesktop",
              DesktopPreferences.allows(origin: origin, frameURL: message.frameInfo.request.url, mainFrame: message.frameInfo.isMainFrame),
              let patch = message.body as? [String: Any] else { return }
        desktopPreferences?.update(patch)
    }

    /// Top find bar (when shown), bottom status bar, web view between them.
    /// Called on resize and on every find-bar toggle so resizing the window
    /// never strands a view at its old frame.
    private func layoutViews() {
        guard let contentView = window?.contentView, let webView, let statusBar, let statusLabel, let statusSpinner, let findBar, let findField, let findPreviousButton, let findNextButton, let findDoneButton, let findResultLabel else { return }
        let bounds = contentView.bounds
        var remaining = bounds
        if !findBar.isHidden {
            findBar.frame = NSRect(x: 0, y: bounds.maxY - 36, width: bounds.width, height: 36)
            let fieldWidth = max(120, min(320, bounds.width - 400))
            findField.frame = NSRect(x: 8, y: 7, width: fieldWidth, height: 22)
            findPreviousButton.frame = NSRect(x: findField.frame.maxX + 8, y: 5, width: 84, height: 26)
            findNextButton.frame = NSRect(x: findPreviousButton.frame.maxX + 4, y: 5, width: 64, height: 26)
            findDoneButton.frame = NSRect(x: findNextButton.frame.maxX + 4, y: 5, width: 64, height: 26)
            findResultLabel.frame = NSRect(x: findDoneButton.frame.maxX + 8, y: 8, width: 100, height: 20)
            remaining.size.height -= 36
        }
        statusBar.frame = NSRect(x: 0, y: 0, width: bounds.width, height: 24)
        statusSpinner.frame = NSRect(x: 8, y: 4, width: 16, height: 16)
        statusLabel.frame = NSRect(x: 30, y: 2, width: bounds.width - 38, height: 20)
        webView.frame = NSRect(x: 0, y: 24, width: bounds.width, height: remaining.height - 24)
    }

    private func setStatus(_ text: String, busy: Bool) {
        statusLabel?.stringValue = text
        if busy {
            statusSpinner?.startAnimation(nil)
        } else {
            statusSpinner?.stopAnimation(nil)
        }
    }

    private func startServer() {
        guard !terminating, let webView else { return }
        transitioning = true
        origin = nil
        hasReachedReady = false
        setStatus("Starting Exo…", busy: true)
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
                switch result {
                case .success(let url):
                    // A printed URL is not a healthy connection: the process
                    // may have printed and then died, or bound a port it
                    // cannot serve. Verify it answers HTTP before loading.
                    self.setStatus("Connecting to the Exo server…", busy: true)
                    self.verifyServer(url, launcher: currentLauncher)
                case .failure(let error):
                    self.transitioning = false
                    self.showFailure(error.description)
                }
            }
        }
    }

    /// GETs the page shell at the printed origin with the fragment stripped
    /// (the fragment is never sent to a server, and no token is used: the
    /// shell is served without one). Retries briefly, then fails.
    private func verifyServer(_ url: URL, launcher currentLauncher: ExoWebLauncher, attempt: Int = 1) {
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        components?.fragment = nil
        guard let probe = components?.url else {
            DispatchQueue.main.async { self.verifyFailed(url) }
            return
        }
        var request = URLRequest(url: probe, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 5)
        request.httpMethod = "GET"
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            let ok = (response as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
            DispatchQueue.main.async {
                guard let self, !self.terminating, self.launcher === currentLauncher else { return }
                if ok {
                    self.transitioning = false
                    self.origin = url
                    let controller = self.webView?.configuration.userContentController
                    controller?.removeAllUserScripts()
                    if let preferences = self.desktopPreferences {
                        controller?.addUserScript(WKUserScript(source: preferences.script(origin: url), injectionTime: .atDocumentStart, forMainFrameOnly: true))
                    }
                    self.webView?.load(URLRequest(url: url))
                } else if attempt < 3 {
                    DispatchQueue.global().asyncAfter(deadline: .now() + 0.5) {
                        self.verifyServer(url, launcher: currentLauncher, attempt: attempt + 1)
                    }
                } else {
                    self.transitioning = false
                    self.verifyFailed(url)
                }
            }
        }.resume()
    }

    private func verifyFailed(_ url: URL) {
        // Host and port only: the printed URL's fragment token never appears
        // in any message, log or persisted state.
        let hostPort = "\(url.host ?? "localhost"):\(url.port ?? 0)"
        showFailure("The Exo web server did not answer at \(hostPort).")
    }

    private func showFailure(_ message: String) {
        guard !terminating, !transitioning, !showingFailure else { return }
        showingFailure = true
        setStatus("Failed", busy: false)
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

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard webView === self.webView, !transitioning, !terminating, let window,
              NativeDialogPolicy.allows(origin: origin, frameURL: frame.request.url,
                                        isMainFrame: frame.isMainFrame) else {
            completionHandler(false)
            return
        }
        let expectedOrigin = origin
        let expectedGeneration = pageGeneration
        let alert = NSAlert()
        alert.messageText = "Confirm action"
        alert.informativeText = String(message.prefix(4000))
        alert.addButton(withTitle: "Cancel")
        alert.addButton(withTitle: "Continue")
        // Make Return explicitly choose the non-destructive action.
        alert.buttons[0].keyEquivalent = "\r"
        // AppKit consumes the Cancel button's Escape equivalent when it becomes the
        // Return default. Handle Escape only for this sheet, for its lifetime.
        var escapeMonitor: Any?
        escapeMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak alert] event in
            guard let alert, event.window === alert.window, event.keyCode == 53,
                  event.modifierFlags.intersection([.command, .control, .option]).isEmpty else { return event }
            alert.buttons[0].performClick(nil)
            return nil
        }
        alert.beginSheetModal(for: window) { result in
            if let monitor = escapeMonitor { NSEvent.removeMonitor(monitor) }
            completionHandler(result == .alertSecondButtonReturn && self.webView === webView
                              && !self.transitioning && !self.terminating
                              && self.origin == expectedOrigin && self.pageGeneration == expectedGeneration)
        }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        guard webView === self.webView, !transitioning, !terminating, let window,
              NativeDialogPolicy.allows(origin: origin, frameURL: frame.request.url,
                                        isMainFrame: frame.isMainFrame) else {
            completionHandler()
            return
        }
        let alert = NSAlert()
        alert.messageText = "Exo"
        alert.informativeText = String(message.prefix(4000))
        alert.addButton(withTitle: "OK")
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        if webView === self.webView { pageGeneration += 1 }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let origin, let current = webView.url,
              current.scheme == origin.scheme, current.host == origin.host, current.port == origin.port else { return }
        hasReachedReady = true
        setStatus("Ready", busy: false)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        // Only before the first Ready: after that, a server exit is reported
        // by onExit, and in-page navigation failures belong to the web app.
        // The error text is not shown: it can name the failing URL.
        guard !hasReachedReady, !terminating, !transitioning, !showingFailure else { return }
        showFailure("The Exo page failed to load.")
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

    // MARK: - Find

    @objc private func showFindBar() {
        guard let findBar, let findField else { return }
        findBar.isHidden = false
        layoutViews()
        window?.makeFirstResponder(findField)
        findField.selectText(nil)
    }

    @objc private func hideFindBar() {
        findBar?.isHidden = true
        findResultLabel?.stringValue = ""
        layoutViews()
        window?.makeFirstResponder(webView)
    }

    @objc private func findNext() {
        runFind(backwards: false)
    }

    @objc private func findPrevious() {
        runFind(backwards: true)
    }

    @objc private func useSelectionForFind() {
        webView?.evaluateJavaScript("window.getSelection().toString()") { [weak self] result, _ in
            DispatchQueue.main.async {
                guard let self, let text = result as? String, !text.isEmpty else { return }
                self.findField?.stringValue = text
                self.showFindBar()
                self.runFind(backwards: false)
            }
        }
    }

    private func runFind(backwards: Bool) {
        guard let webView, let findField else { return }
        let query = findField.stringValue
        guard !query.isEmpty else {
            showFindBar()
            return
        }
        guard let literal = jsString(query) else { return }
        // window.find(query, caseSensitive, backwards, wrapAround,
        // wholeWord, searchInFrames, showDialog). No dialog: the native
        // find bar is the interface.
        webView.evaluateJavaScript("window.find(\(literal), false, \(backwards), true, false, false, false)") { [weak self] result, _ in
            DispatchQueue.main.async {
                self?.findResultLabel?.stringValue = (result as? Bool == true) ? "" : "Not found"
            }
        }
    }

    /// The query as a JSON string literal, so quotes, backslashes and
    /// newlines in the query cannot break out of the script.
    private func jsString(_ value: String) -> String? {
        guard let data = try? JSONSerialization.data(withJSONObject: [value], options: []),
              let text = String(data: data, encoding: .utf8),
              text.count >= 2 else { return nil }
        return String(text.dropFirst().dropLast())
    }

    func control(_ control: NSControl, textView: NSTextView, doCommandBy commandSelector: Selector) -> Bool {
        if commandSelector == #selector(NSResponder.cancelOperation(_:)) {
            hideFindBar()
            return true
        }
        if commandSelector == #selector(NSResponder.insertNewline(_:)) {
            findNext()
            return true
        }
        return false
    }

    // MARK: - Zoom

    @objc private func zoomIn() {
        guard let webView else { return }
        webView.pageZoom = min(3.0, webView.pageZoom * 1.2)
    }

    @objc private func zoomOut() {
        guard let webView else { return }
        webView.pageZoom = max(0.5, webView.pageZoom / 1.2)
    }

    @objc private func resetZoom() {
        webView?.pageZoom = 1.0
    }

    // MARK: - About

    @objc private func showAboutPanel() {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
        let commit = Bundle.main.object(forInfoDictionaryKey: "ExoSourceCommit") as? String ?? "unknown"
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "Exo",
            .applicationVersion: version,
            .version: "Build \(build)",
            .credits: NSAttributedString(string: "Source commit: \(commit)"),
        ])
    }

    private func buildMenu() {
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        let aboutItem = NSMenuItem(title: "About Exo", action: #selector(showAboutPanel), keyEquivalent: "")
        aboutItem.target = self
        appMenu.addItem(aboutItem)
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(title: "Quit Exo", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        let exoMenuItem = NSMenuItem()
        let exoMenu = NSMenu(title: "Exo")
        let reloadItem = NSMenuItem(title: "Reload Page", action: #selector(reloadPage), keyEquivalent: "r")
        reloadItem.target = self
        exoMenu.addItem(reloadItem)
        if !isAttached {
            let stopItem = NSMenuItem(title: "Stop Core", action: #selector(stopCore), keyEquivalent: "")
            stopItem.target = self
            exoMenu.addItem(stopItem)
        }
        exoMenuItem.submenu = exoMenu
        mainMenu.addItem(exoMenuItem)

        let viewMenuItem = NSMenuItem()
        let viewMenu = NSMenu(title: "View")
        let zoomInItem = NSMenuItem(title: "Zoom In", action: #selector(zoomIn), keyEquivalent: "+")
        zoomInItem.target = self
        viewMenu.addItem(zoomInItem)
        let zoomOutItem = NSMenuItem(title: "Zoom Out", action: #selector(zoomOut), keyEquivalent: "-")
        zoomOutItem.target = self
        viewMenu.addItem(zoomOutItem)
        let resetZoomItem = NSMenuItem(title: "Actual Size", action: #selector(resetZoom), keyEquivalent: "0")
        resetZoomItem.target = self
        viewMenu.addItem(resetZoomItem)
        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)

        let editItem = NSMenuItem()
        let edit = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            edit.addItem(NSMenuItem(title: title, action: Selector(action), keyEquivalent: key))
        }
        edit.addItem(.separator())
        let findMenu = NSMenu(title: "Find")
        let findItem = NSMenuItem(title: "Find…", action: #selector(showFindBar), keyEquivalent: "f")
        findItem.target = self
        findMenu.addItem(findItem)
        let findNextItem = NSMenuItem(title: "Find Next", action: #selector(findNext), keyEquivalent: "g")
        findNextItem.target = self
        findMenu.addItem(findNextItem)
        let findPreviousItem = NSMenuItem(title: "Find Previous", action: #selector(findPrevious), keyEquivalent: "g")
        findPreviousItem.keyEquivalentModifierMask = [.command, .shift]
        findPreviousItem.target = self
        findMenu.addItem(findPreviousItem)
        let useSelectionItem = NSMenuItem(title: "Use Selection for Find", action: #selector(useSelectionForFind), keyEquivalent: "e")
        useSelectionItem.target = self
        findMenu.addItem(useSelectionItem)
        let findSubmenuItem = NSMenuItem()
        findSubmenuItem.title = "Find"
        findSubmenuItem.submenu = findMenu
        edit.addItem(findSubmenuItem)
        editItem.submenu = edit
        mainMenu.addItem(editItem)

        let windowMenuItem = NSMenuItem()
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(NSMenuItem(title: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m"))
        windowMenu.addItem(NSMenuItem(title: "Zoom Window", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: ""))
        windowMenu.addItem(NSMenuItem(title: "Close", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w"))
        windowMenuItem.submenu = windowMenu
        mainMenu.addItem(windowMenuItem)
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
