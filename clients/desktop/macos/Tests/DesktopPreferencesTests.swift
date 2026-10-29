import Foundation

@main struct DesktopPreferencesTests {
    static func main() {
        let suite = "exo-native-test-" + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = DesktopPreferences(defaults: defaults, scope: "seat-a")
        first.update(["view": "providers", "thread": "s_first", "scroll": 0.7,
                      "appearance": "light", "petMode": "off", "layout": "classic",
                      "token": "must-not-persist", "draft": "must-not-persist"])
        let restored = DesktopPreferences(defaults: UserDefaults(suiteName: suite)!, scope: "seat-a")
        precondition(restored.snapshot["thread"] as? String == "s_first")
        precondition(restored.snapshot["appearance"] as? String == "light")
        precondition(restored.snapshot.count == 6)
        precondition(DesktopPreferences(defaults: defaults, scope: "seat-b").snapshot.isEmpty)
        restored.update(["thread": NSNull(), "scroll": NSNull(), "view": "chat"])
        precondition(restored.snapshot["thread"] == nil && restored.snapshot["scroll"] == nil)
        for value: Any in [true, -1, 2, Double.infinity, Double.nan] {
            precondition(DesktopPreferences.clean(["scroll": value]).isEmpty)
        }
        precondition(DesktopPreferences.clean(["thread": "bad\ntext", "appearance": "custom", "petMode": "network"]).isEmpty)
        precondition(DesktopPreferences.clean(["thread": "https://private.example/path"]).isEmpty)
        let old = URL(string: "http://127.0.0.1:7342/")!
        let new = URL(string: "http://127.0.0.1:54321/#access-token")!
        precondition(DesktopPreferences.allows(origin: new, frameURL: new, mainFrame: true))
        precondition(!DesktopPreferences.allows(origin: new, frameURL: old, mainFrame: true))
        precondition(!DesktopPreferences.allows(origin: new, frameURL: new, mainFrame: false))
        let script = restored.script(origin: new)
        precondition(script.contains("54321") && !script.contains("access-token") && !script.contains("must-not-persist"))
        precondition(script.contains("light") && !script.contains("7342"))
        print("PASS: scoped preferences, recreated defaults, deletion, strict values, changed port and token exclusion")
    }
}
