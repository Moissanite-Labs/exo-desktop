"""Native-only composition validates layout schema and origin without web assets."""
import pathlib
import subprocess


def test_native_layout_schema_uses_only_private_test_defaults(tmp_path):
    source = pathlib.Path(__file__).resolve().parents[1] / 'Sources/ExoDesktop/PanePreferences.swift'
    main = tmp_path / 'main.swift'
    main.write_text('''import Foundation
let suite = "exo-pane-test-" + UUID().uuidString
let defaults = UserDefaults(suiteName: suite)!
defer { defaults.removePersistentDomain(forName: suite) }
let prefs = PanePreferences(defaults: defaults, origin: { nil })
let good: [String: Any] = ["version": 1, "order": ["threads","conversation","details"], "threads":224,"details":340,"collapsed":[]]
precondition(prefs.validate(good) != nil)
for (key,value) in [("version",true as Any),("threads",159 as Any),("details",521 as Any),("token","private" as Any),("collapsed",["conversation"] as Any),("order",["threads","threads","details"] as Any)] {
 var bad=good;bad[key]=value;precondition(prefs.validate(bad) == nil)
}
defaults.set(good, forKey:"ExoPaneLayoutV1")
let reopened = PanePreferences(defaults: defaults, origin: { nil })
precondition(reopened.validate(defaults.dictionary(forKey:"ExoPaneLayoutV1")) != nil)
let current=URL(string:"http://127.0.0.1:43210/#token=not-persisted")!
precondition(PanePreferences.allows(current:current,mainFrame:true,scheme:"http",host:"127.0.0.1",port:43210))
precondition(!PanePreferences.allows(current:current,mainFrame:false,scheme:"http",host:"127.0.0.1",port:43210))
precondition(!PanePreferences.allows(current:current,mainFrame:true,scheme:"http",host:"127.0.0.1",port:43211))
precondition(!PanePreferences.allows(current:current,mainFrame:true,scheme:"https",host:"127.0.0.1",port:43210))
precondition(!PanePreferences.allows(current:URL(string:"http://evil.test:43210"),mainFrame:true,scheme:"http",host:"evil.test",port:43210))
precondition(!PanePreferences.allows(current:nil,mainFrame:true,scheme:"http",host:"127.0.0.1",port:43210))
print("native layout schema pass")
''')
    binary = tmp_path / 'test-layout'
    subprocess.run(['swiftc', str(source), str(main), '-framework', 'WebKit', '-o', str(binary)], check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)
