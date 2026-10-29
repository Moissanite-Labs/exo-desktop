extension AppDelegate {
 func acceptance(_ url: URL) {
  precondition(Self.configuredPreferences() == nil, "unconfigured build must not bridge preferences")
  NSApp.setActivationPolicy(.accessory)
  let w=NSWindow(contentRect:NSRect(x:100,y:100,width:600,height:400),styleMask:[.titled],backing:.buffered,defer:false)
  if CommandLine.arguments[3] == "restore" {
   precondition(w.setFrameUsingName(frameAutosaveName), "native frame must restore across relaunch")
  }
  let config=WKWebViewConfiguration(); config.websiteDataStore = .nonPersistent()
  config.userContentController.add(self,name:"exoDesktop")
  config.userContentController.addUserScript(WKUserScript(source:desktopPreferences!.script(origin:url),injectionTime:.atDocumentStart,forMainFrameOnly:true))
  let v=WKWebView(frame:w.contentView!.bounds,configuration:config)
  self.webView=v; self.window=w; self.origin=url; self.transitioning=false
  w.contentView!.addSubview(v); w.orderFront(nil); v.load(URLRequest(url:url))
  func wait(_ condition:()->Bool) { let deadline=Date().addingTimeInterval(10); while !condition() && Date()<deadline {RunLoop.current.run(until:Date().addingTimeInterval(0.01))};precondition(condition(),"native prefs timed out") }
  wait {!v.isLoading && v.url != nil}
  var initial:[String:Any]?
  v.evaluateJavaScript("window.__exoDesktopPrefs") { value,_ in initial=value as? [String:Any] }
  wait {initial != nil}; precondition(initial?["thread"] as? String == (CommandLine.arguments[3] == "seed" ? "s_restored" : "s_new"))
  precondition(initial?["appearance"] as? String == (CommandLine.arguments[3] == "seed" ? "light" : "system"))
  let js="window.webkit.messageHandlers.exoDesktop.postMessage({thread:'s_new',appearance:'system',petMode:'off',token:'never-save'});true"
  v.evaluateJavaScript(js) {_,_ in}
  wait {self.desktopPreferences!.snapshot["thread"] as? String == "s_new"}
  precondition(desktopPreferences!.snapshot["token"]==nil)
  let before=desktopPreferences!.snapshot as NSDictionary
  self.origin=URL(string:"http://127.0.0.1:1/")!
  var done=false
  v.evaluateJavaScript("window.webkit.messageHandlers.exoDesktop.postMessage({thread:'wrong_origin'});true") {_,_ in done=true}
  wait {done}; RunLoop.current.run(until:Date().addingTimeInterval(0.1))
  precondition(desktopPreferences!.snapshot as NSDictionary == before)
  self.origin=url
  v.evaluateJavaScript("const f=document.createElement('iframe');f.src='"+url.absoluteString+"';f.onload=()=>{f.contentWindow.webkit.messageHandlers.exoDesktop.postMessage({thread:'subframe'});window.frameDone=true};document.body.append(f);true") {_,_ in}
  var frameDone=false
  wait {if frameDone{return true};v.evaluateJavaScript("window.frameDone===true") {value,_ in frameDone=value as? Bool ?? false};return false}
  precondition(desktopPreferences!.snapshot as NSDictionary == before)
  windowDidMove(Notification(name:NSWindow.didMoveNotification)); UserDefaults.standard.synchronize()
  config.userContentController.removeScriptMessageHandler(forName:"exoDesktop"); v.stopLoading(); w.close()
  print("PASS native injection, accepted mainframe update, wrong-origin and subframe refusal")
 }
}
let application=NSApplication.shared
let suite=CommandLine.arguments[2]
let defaults=UserDefaults(suiteName:suite)!
let preferences=DesktopPreferences(defaults:defaults,scope:"fixture-core")
if CommandLine.arguments[3] == "seed" { preferences.update(["thread":"s_restored","appearance":"light"]) }
let delegate=AppDelegate(preferences:preferences)
delegate.acceptance(URL(string:CommandLine.arguments[1])!)
let relaunched=DesktopPreferences(defaults:UserDefaults(suiteName:suite)!,scope:"fixture-core")
precondition(relaunched.snapshot["thread"] as? String == "s_new")
precondition(relaunched.snapshot["appearance"] as? String == "system")
if CommandLine.arguments[3] == "restore" { defaults.removePersistentDomain(forName:suite) }
defaults.synchronize()
