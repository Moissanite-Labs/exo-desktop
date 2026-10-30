import http.server, threading, tempfile, pathlib, subprocess, os

root = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            b"<html><body>Disposable native acceptance fixture</body></html>"
        )

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix="exo-native-dialog-") as d:
    p = pathlib.Path(d)
    src = (
        (root / "Sources/ExoDesktop/main.swift")
        .read_text()
        .split("\nlet delegate = AppDelegate()")[0]
    )
    src += """
extension AppDelegate {
 func acceptance(_ url: URL) {
  setbuf(stdout, nil)
  NSApp.setActivationPolicy(.accessory)
  NSApp.activate(ignoringOtherApps:true)
  let w = NSWindow(contentRect: NSRect(x:100,y:100,width:600,height:400),styleMask:[.titled],backing:.buffered,defer:false)
  let v = WKWebView(frame:w.contentView!.bounds)
  self.window=w; self.webView=v; self.origin=url; v.uiDelegate=self
  w.contentView!.addSubview(v); w.orderFront(nil); v.load(URLRequest(url:url))
  func wait(_ condition: () -> Bool) { let deadline=Date().addingTimeInterval(10); while !condition() && Date()<deadline { RunLoop.current.run(until:Date().addingTimeInterval(0.01)) }; precondition(condition(),"native acceptance timed out") }
  wait { !v.isLoading && v.url != nil }
  func buttons(_ view:NSView) -> [NSButton] { (view as? NSButton).map{[$0]} ?? view.subviews.flatMap{buttons($0)} }
  func confirm(_ title:String, expected:Bool, allowed:Bool=true) {
   var result:Bool?; var error:Error?
   v.evaluateJavaScript("confirm('Disposable fixture')") { value,err in result=value as? Bool; error=err }
   if allowed {
    wait { w.attachedSheet != nil }
    let sheet=w.attachedSheet!; let all=buttons(sheet.contentView!)
    precondition(all.contains{$0.title=="Cancel"} && all.contains{$0.title=="Continue"})
    precondition(sheet.defaultButtonCell?.title == "Cancel", "Return default must be Cancel")
    if title=="transition during sheet" { self.transitioning=true }
    if title=="origin replaced during sheet" { self.origin=URL(string:"http://127.0.0.1:1/")! }
    if title=="navigation during sheet" { self.pageGeneration += 1 }
    if title=="Escape" || title=="Return" {
     sheet.makeKeyAndOrderFront(nil)
     RunLoop.current.run(until:Date().addingTimeInterval(0.3))
     let character=String(UnicodeScalar(title=="Escape" ? 27 : 13)!)
     let event=NSEvent.keyEvent(with:.keyDown,location:.zero,modifierFlags:[],timestamp:ProcessInfo.processInfo.systemUptime,windowNumber:sheet.windowNumber,context:nil,characters:character,charactersIgnoringModifiers:character,isARepeat:false,keyCode:title=="Escape" ? 53 : 36)!
     NSApp.sendEvent(event)
    } else { all.first{$0.title==(title.contains("during sheet") ? "Continue" : title)}!.performClick(nil) }
   }
   wait { result != nil || error != nil }; precondition(error==nil && result==expected)
   print("PASS native confirm \\(title) expected \\(expected)")
  }
  confirm("Cancel",expected:false); confirm("Continue",expected:true)
  confirm("Return",expected:false)
  confirm("Escape",expected:false)
  confirm("transition during sheet",expected:false); self.transitioning=false
  confirm("origin replaced during sheet",expected:false); self.origin=url
  confirm("navigation during sheet",expected:false)
  self.transitioning=true
  confirm("restart pending",expected:false,allowed:false)
  self.transitioning=false
  self.origin=URL(string:"http://127.0.0.1:1/")!
  confirm("wrong origin",expected:false,allowed:false)
  self.origin=url
  var frameResult:Bool?
  v.evaluateJavaScript("window.frameResult=null; const f=document.createElement('iframe'); f.src='"+url.absoluteString+"'; f.onload=()=>{window.frameResult=f.contentWindow.confirm('subframe')}; document.body.append(f); true") {_,_ in}
  wait { if frameResult != nil{return true}; v.evaluateJavaScript("window.frameResult") {value,_ in frameResult=value as? Bool}; return false }
  precondition(frameResult==false && w.attachedSheet==nil); print("PASS native subframe refused")
  w.close()
 }
}
let application = NSApplication.shared
let testDelegate=AppDelegate()
testDelegate.acceptance(URL(string:CommandLine.arguments[1])!)
"""
    (p / "main.swift").write_text(src)
    subprocess.run(
        [
            "swiftc",
            str(p / "main.swift"),
            *[
                str(path)
                for path in sorted((root / "Sources/ExoDesktop").glob("*.swift"))
                if path.name != "main.swift"
            ],
            "-framework",
            "AppKit",
            "-framework",
            "WebKit",
            "-o",
            str(p / "probe"),
        ],
        check=True,
    )
    home = p / "home"
    home.mkdir()
    subprocess.run(
        [str(p / "probe"), f"http://127.0.0.1:{server.server_port}/"],
        env=dict(os.environ, HOME=str(home), CFFIXED_USER_HOME=str(home)),
        check=True,
        timeout=45,
    )
server.shutdown()
