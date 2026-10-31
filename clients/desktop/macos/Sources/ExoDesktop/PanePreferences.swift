import Foundation
import CoreFoundation
import WebKit

// This bridge accepts one versioned layout schema, never general preferences.
final class PanePreferences: NSObject, WKScriptMessageHandlerWithReply {
    private let origin: () -> URL?
    private let defaults: UserDefaults
    private let key = "ExoPaneLayoutV1"
    private let ids: Set<String> = ["threads", "conversation", "details"]

    init(defaults: UserDefaults = .standard, origin: @escaping () -> URL?) {
        self.defaults = defaults
        self.origin = origin
    }

    static func integer(_ value: Any?, min: Int, max: Int) -> Int? {
        guard let number = value as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue.isFinite,
              number.doubleValue == Double(number.intValue),
              (min...max).contains(number.intValue) else { return nil }
        return number.intValue
    }

    func validate(_ value: Any?) -> [String: Any]? {
        guard let layout = value as? [String: Any],
              Set(layout.keys) == Set(["version", "order", "threads", "details", "collapsed"]),
              Self.integer(layout["version"], min: 1, max: 1) != nil,
              let order = layout["order"] as? [String], order.count == 3, Set(order) == ids,
              let collapsed = layout["collapsed"] as? [String],
              Set(collapsed).count == collapsed.count,
              Set(collapsed).isSubset(of: ["threads", "details"]),
              let threads = Self.integer(layout["threads"], min: 160, max: 520),
              let details = Self.integer(layout["details"], min: 160, max: 520) else { return nil }
        return ["version": 1, "order": order, "threads": threads, "details": details, "collapsed": collapsed]
    }

    static func allows(current: URL?, mainFrame: Bool, scheme: String, host: String, port: Int) -> Bool {
        guard mainFrame, let current, current.scheme == "http",
              ["127.0.0.1", "localhost", "::1"].contains(current.host ?? "") else { return false }
        return scheme == current.scheme && host == current.host && port == current.port
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                               replyHandler: @escaping (Any?, String?) -> Void) {
        guard message.name == "exoPaneLayout",
              Self.allows(current: origin(), mainFrame: message.frameInfo.isMainFrame,
                          scheme: message.frameInfo.securityOrigin.protocol,
                          host: message.frameInfo.securityOrigin.host,
                          port: message.frameInfo.securityOrigin.port),
              let body = message.body as? [String: Any], let action = body["action"] as? String else {
            replyHandler(nil, "Layout request refused"); return
        }
        if action == "load", Set(body.keys) == ["action"] {
            replyHandler(validate(defaults.dictionary(forKey: key)) ?? NSNull(), nil)
        } else if action == "save", Set(body.keys) == ["action", "layout"], let layout = validate(body["layout"]) {
            defaults.set(layout, forKey: key)
            replyHandler(layout, nil)
        } else {
            replyHandler(nil, "Invalid layout request")
        }
    }
}
