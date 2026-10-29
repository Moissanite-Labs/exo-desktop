extension AppDelegate {
 func workspaceAcceptance(_ url:URL, phase:String) {
  setbuf(stdout,nil); NSApp.setActivationPolicy(.accessory)
  let w=NSWindow(contentRect:NSRect(x:100,y:100,width:1200,height:850),styleMask:[.titled],backing:.buffered,defer:false)
  let configuration=WKWebViewConfiguration(); configuration.websiteDataStore = .nonPersistent()
  configuration.userContentController.add(self,name:"exoDesktop")
  let v=WKWebView(frame:w.contentView!.bounds,configuration:configuration)
  self.window=w; self.webView=v; v.navigationDelegate=self; v.uiDelegate=self
  w.contentView!.addSubview(v);w.orderFront(nil)
  func wait(_ label:String,_ predicate:()->Bool) {
   let deadline=Date().addingTimeInterval(25)
   while !predicate() && Date()<deadline {RunLoop.current.run(until:Date().addingTimeInterval(0.02))}
   precondition(predicate(),"composed WK timeout: "+label)
  }
  func js(_ source:String)->Any? {
   var done=false;var result:Any?;var error:Error?
   v.evaluateJavaScript(source){value,err in result=value;error=err;done=true}
   wait("javascript completion"){done}
   precondition(error==nil,"JS error: "+String(describing:error)+" source "+source)
   return result
  }
  func expect(_ label:String,_ source:String) { wait(label){ js(source) as? Bool == true };print("PASS composed WK "+label) }
  var firstLoad=true
  func loadFixture() {
   let priorGeneration=self.pageGeneration
   self.transitioning=true;self.origin=nil
   self.verifyServer(url,launcher:self.launcher)
   wait("verified page"){!self.transitioning}
   if phase=="list-failure" && firstLoad {
    expect("mode control during held bootstrap","!!document.querySelector('.xc-pet-mode')")
    _=js("(()=>{const p=document.querySelector('.xc-pet-mode');p.value='off';p.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
    wait("early Off reached native copy"){self.desktopPreferences!.snapshot["petMode"] as? String == "off"}
    print("PASS composed WK early Off persisted before bootstrap finished")
    try! "release".write(toFile:CommandLine.arguments[5],atomically:true,encoding:.utf8)
   }
   firstLoad=false
   if self.pageGeneration==priorGeneration && v.url != nil {v.reload()}
   wait("new page navigation"){self.pageGeneration>priorGeneration && !v.isLoading && !self.transitioning}
   expect("application shell","!!document.querySelector('.xc-appearance') && !!document.querySelector('.xc-pet-mode')")
  }
  loadFixture()
  if phase=="list-failure" {
   expect("initial session-list failure visible","document.body.textContent.includes('Synthetic initial list unavailable')")
   // A transport failure is not evidence that the remembered thread was removed.
   precondition(desktopPreferences!.snapshot["thread"] as? String == "s2", "failed list erased native thread")
   precondition(abs((desktopPreferences!.snapshot["scroll"] as? Double ?? -1)-0.37)<0.001, "failed list erased native reading")
   print("PASS composed WK initial list 503 preserved native thread and reading")
   try! "release".write(toFile:CommandLine.arguments[4],atomically:true,encoding:.utf8)
   loadFixture()
  }
  if phase != "restore" {
   _=js("(()=>{const p=document.querySelector('.xc-pet-mode');p.value='full';p.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
   expect("seed appearance and pet","document.documentElement.dataset.theme==='light' && document.querySelector('.xc-pet-mode').value==='full'")
   expect("seed chat+thread+layout","document.querySelector('.xc-nav-link[aria-current]')?.textContent==='Chat' && document.querySelector('.xc-log')?.textContent.includes('native snapshot s2') && localStorage.getItem('xc-layout')==='classic' && document.querySelectorAll('.xc-msg').length>100")
   expect("incoming event retained during saved GET","document.querySelector('.xc-log')?.textContent.includes('native incoming during restore')")
   expect("seed reading fraction","(()=>{const l=document.querySelector('.xc-log');return Math.abs(l.scrollTop/(l.scrollHeight-l.clientHeight)-.37)<.04})()")
   expect("pending pet composition","document.querySelector('.xc-pet-growth')?.textContent.includes('300 XP banked') && document.querySelector('.xc-pet-card svg')?.dataset.form==='egg'")
   _=js("(()=>{const s=document.querySelector('.xc-appearance');s.value='system';s.dispatchEvent(new Event('change',{bubbles:true}));const p=document.querySelector('.xc-pet-mode');p.value='off';p.dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('.xc-layout').click();[...document.querySelectorAll('.xc-sess')].find(x=>x.textContent.startsWith('s1')).click();return true})()")
   expect("changed selected thread","document.querySelector('.xc-sess.on')?.textContent.startsWith('s1') && document.querySelectorAll('.xc-msg').length>100")
   _=js("(()=>{const l=document.querySelector('.xc-log');l.scrollTop=(l.scrollHeight-l.clientHeight)*.42;l.dispatchEvent(new Event('scroll'));return true})()")
   wait("native reading saved"){abs((self.desktopPreferences!.snapshot["scroll"] as? Double ?? -1)-0.42)<0.04}
   _=js("document.querySelector('a[href=\"#tasks\"]').click();true")
   expect("changed native route","document.querySelector('.xc-nav-link[aria-current]')?.textContent==='Tasks'")
   wait("native choices saved"){self.desktopPreferences!.snapshot["view"] as? String == "tasks" && self.desktopPreferences!.snapshot["appearance"] as? String == "system" && self.desktopPreferences!.snapshot["petMode"] as? String == "off"}
   loadFixture()
  }
  expect("restored route+appearance+pet mode","document.querySelector('.xc-nav-link[aria-current]')?.textContent==='Tasks' && document.documentElement.dataset.theme==='system' && document.querySelector('.xc-pet-mode').value==='off' && document.querySelectorAll('.xc-pet-glyph svg').length===0")
  _=js("document.querySelector('a[href=\"#chat\"]').click();true")
  expect("restored thread+layout","document.querySelector('.xc-sess.on')?.textContent.startsWith('s1') && localStorage.getItem('xc-layout')==='inverse' && document.querySelectorAll('.xc-msg').length>100")
  expect("restored reading fraction","(()=>{const l=document.querySelector('.xc-log');return Math.abs(l.scrollTop/(l.scrollHeight-l.clientHeight)-.42)<.04})()")
  precondition(!self.desktopPreferences!.snapshot.keys.contains("token"))
  // Preserve a non-Chat route so the next process proves route restoration too.
  _=js("document.querySelector('a[href=\"#tasks\"]').click();true")
  wait("final route saved"){self.desktopPreferences!.snapshot["view"] as? String == "tasks"}
  configuration.userContentController.removeScriptMessageHandler(forName:"exoDesktop");v.stopLoading();w.close()
 }
}
let application=NSApplication.shared
let defaults=UserDefaults(suiteName:CommandLine.arguments[2])!
let preferences=DesktopPreferences(defaults:defaults,scope:"fixture-core")
if CommandLine.arguments[3] != "restore" {
 preferences.update(["view":"chat","thread":"s2","layout":"classic","appearance":"light","petMode":"full","scroll":0.37])
}
let delegate=AppDelegate(preferences:preferences)
delegate.workspaceAcceptance(URL(string:CommandLine.arguments[1])!,phase:CommandLine.arguments[3])
defaults.synchronize()
if CommandLine.arguments[3]=="restore" {defaults.removePersistentDomain(forName:CommandLine.arguments[2])}
