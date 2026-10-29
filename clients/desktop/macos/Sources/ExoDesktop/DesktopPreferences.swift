import Foundation
import CoreFoundation

/// A port-independent copy of UI choices only. Never stores auth, drafts or transcript text.
final class DesktopPreferences {
    private let defaults: UserDefaults
    private let key: String
    init(defaults: UserDefaults = .standard, scope: String) {
        precondition(!scope.isEmpty)
        self.defaults = defaults
        self.key = "ExoDesktopUIPrefsV1." + scope
    }

    static func clean(_ input: [String: Any]) -> [String: Any] {
        var result: [String: Any] = [:]
        let enums = ["view": ["chat", "tasks", "schedule", "command", "providers"],
                     "layout": ["inverse", "classic"], "appearance": ["dark", "light", "system"],
                     "petMode": ["mini", "full", "off"]]
        for (key, allowed) in enums {
            if let value = input[key] as? String, allowed.contains(value) { result[key] = value }
        }
        if let thread = input["thread"] as? String, !thread.isEmpty, thread.count <= 200,
           thread.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 95 || $0 == 45 }) {
            result["thread"] = thread
        }
        if let value = input["scroll"] as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID(),
           value.doubleValue.isFinite, (0...1).contains(value.doubleValue) { result["scroll"] = value.doubleValue }
        return result
    }

    var snapshot: [String: Any] { Self.clean(defaults.dictionary(forKey: key) ?? [:]) }
    func update(_ patch: [String: Any]) {
        var value = snapshot
        for (key, item) in Self.clean(patch) { value[key] = item }
        // A new conversation or a removed thread must clear the previous pointer.
        for key in ["thread", "scroll"] where patch[key] is NSNull { value.removeValue(forKey: key) }
        defaults.set(value, forKey: key)
    }

    static func allows(origin: URL?, frameURL: URL?, mainFrame: Bool) -> Bool {
        guard mainFrame, let origin, let frameURL,
              origin.scheme == "http", ["127.0.0.1", "localhost", "::1"].contains(origin.host ?? ""),
              origin.scheme == frameURL.scheme, origin.host == frameURL.host,
              origin.port == frameURL.port else { return false }
        return true
    }

    func script(origin: URL) -> String {
        var parts = URLComponents(url: origin, resolvingAgainstBaseURL: false)!
        parts.path = ""; parts.query = nil; parts.fragment = nil
        let data = try! JSONSerialization.data(withJSONObject: ["origin": parts.string!, "prefs": snapshot], options: [.sortedKeys])
        let json = String(data: data, encoding: .utf8)!
        return "(() => { const state = \(json); if (location.origin === state.origin) window.__exoDesktopPrefs = state.prefs; })();"
    }
}
