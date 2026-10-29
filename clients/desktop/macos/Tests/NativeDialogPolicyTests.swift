import Foundation

@main struct DialogPolicyTests {
    static func main() {
        let origin = URL(string: "http://127.0.0.1:43210")!
        let cases: [(String?, Bool, Bool)] = [
            ("http://127.0.0.1:43210/providers", true, true),
            ("http://127.0.0.1:43210/chat#private", true, true),
            ("http://127.0.0.1:43210/providers", false, false),
            ("http://127.0.0.1:43211/providers", true, false),
            ("http://localhost:43210/providers", true, false),
            ("https://127.0.0.1:43210/providers", true, false),
            ("https://example.invalid", true, false),
            ("file:///tmp/page.html", true, false),
            (nil, true, false)
        ]
        for (url, main, expected) in cases {
            precondition(NativeDialogPolicy.allows(origin: origin, frameURL: url.flatMap(URL.init(string:)),
                                                   isMainFrame: main) == expected)
        }
        precondition(!NativeDialogPolicy.allows(origin: nil, frameURL: origin, isMainFrame: true))
    }
}
