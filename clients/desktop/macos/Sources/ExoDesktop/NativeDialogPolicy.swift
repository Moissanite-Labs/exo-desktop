import Foundation

/// Only the connected first-party document may ask the native shell for a dialog.
enum NativeDialogPolicy {
    static func allows(origin: URL?, frameURL: URL?, isMainFrame: Bool) -> Bool {
        guard isMainFrame, let origin, let frameURL,
              ["http", "https"].contains(origin.scheme ?? ""),
              frameURL.scheme == origin.scheme,
              frameURL.host == origin.host,
              frameURL.port == origin.port else { return false }
        return true
    }
}
