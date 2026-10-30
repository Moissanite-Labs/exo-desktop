"""Search and keyboard selection through the actual browser DOM. No real core or credentials."""
import pytest

from browser import Browser, Served, find_chrome
from test_chat import FakeSource

pytestmark = pytest.mark.skipif(not find_chrome(), reason='Chrome is unavailable')


@pytest.fixture
def page():
    pytest.importorskip('websockets.sync.client')
    web = Served(FakeSource())
    browser = Browser()
    browser.goto(web.url())
    browser.wait('document.readyState === "complete"')
    try:
        yield browser
    finally:
        browser.close()
        web.close()


def prepare(page, extra=''):
    page.eval('''(async()=>{
      const {createModelPicker} = await import('/static/model_picker.js');
      window.applied=[]; window.cancelled=0;
      window.picker=createModelPicker({label:'Main model', selected:'alpha:sonnet',
        rows:[{route:'alpha:sonnet',name:'Sonnet',provider:'Alpha'},
              {route:'beta:sonnet',name:'Sonnet',provider:'Beta'},
              {route:'openai:gpt-fast',name:'GPT Fast',provider:'OpenAI'},
              {route:'beta:sonnet',name:'duplicate'}],
        onCancel:()=>{window.cancelled++;document.querySelector('#return-focus').focus()},
        onApply:async route=>{window.applied.push(route);''' + extra + '''}});
      document.body.replaceChildren(picker.element);
      const button=document.createElement('button');button.id='return-focus';document.body.append(button);
      picker.focus();
    })()''')


def search(page, text):
    page.eval('(()=>{const field=document.querySelector("[role=combobox]");field.focus();field.value=' + repr(text) + ';field.dispatchEvent(new Event("input",{bubbles:true}));})()')


def key(page, value):
    page.eval('document.querySelector("[role=combobox]").dispatchEvent(new KeyboardEvent("keydown",{key:' + repr(value) + ',bubbles:true,cancelable:true}))')


def test_filter_keyboard_chooses_exact_route_without_applying_while_typing(page):
    prepare(page)
    assert page.eval('document.querySelectorAll("[role=option]").length') == 3
    search(page, 'sonnet')
    assert page.eval('applied.length') == 0
    assert page.eval('document.querySelectorAll("[role=option]").length') == 2
    key(page, 'ArrowDown')
    assert page.eval('document.querySelector("[aria-selected=true]").textContent') == 'Sonnetbeta:sonnet'
    key(page, 'Enter')
    page.wait('applied.length === 1')
    assert page.eval('applied') == ['beta:sonnet']
    search(page, 'openai fast')
    key(page, 'Enter')
    page.wait('applied.length === 2')
    assert page.eval('applied') == ['beta:sonnet', 'openai:gpt-fast']
    key(page, 'Escape')
    assert page.eval('cancelled === 1 && document.activeElement.id === "return-focus"')


def test_empty_loading_error_and_pending_duplicate_guards(page):
    prepare(page, 'await new Promise(resolve=>window.release=resolve);')
    search(page, 'no such model')
    key(page, 'Enter')
    assert page.eval('applied.length === 0 && document.querySelector("[role=status]").textContent.includes("No matching")')
    search(page, 'beta')
    key(page, 'Enter')
    key(page, 'Enter')
    page.wait('applied.length === 1')
    assert page.eval('document.querySelector("[role=combobox]").disabled')
    page.eval('release()')
    page.wait('!document.querySelector("[role=combobox]").disabled')
    page.eval('picker.setError("Models failed to load")')
    assert page.eval('document.querySelector("[role=status]").textContent === "Models failed to load"')
    assert page.eval('document.querySelector(".xc-primary").disabled')
    page.eval('picker.setRows([])')
    assert page.eval('document.querySelector("[role=status]").textContent.includes("No models listed")')


# The page fixture also boots the chat view, whose status refreshes (`/command` context, findings) can land after
# mount_view swaps in its fetch. Count only the Providers view's own writes.
PROVIDER_POSTS = 'posts.filter(p=>p.path.startsWith("/api/providers/"))'


def mount_view(page, view, applied='true'):
    page.eval(r'''(async()=>{
      window.posts=[];
      const models={models:[{route:'alpha:sonnet',name:'Sonnet',provider:'Alpha'}],
                    available:[{route:'beta:sonnet',name:'Sonnet',provider:'Beta'}]};
      window.fetch=async (path,opt={})=>{
        if(opt.method==='POST') posts.push({path,body:JSON.parse(opt.body||'{}')});
        let data={};
        if(path.endsWith('/models'))data=models;
        else if(path==='/api/providers')data={providers:[],ready:true};
        else if(path==='/api/providers/default')data={applied:''' + applied + r'''};
        else if(path==='/api/complete/commands')data={commands:[{name:'model'},{name:'default'}],core:[],client:[],guidance:false};
        else if(path==='/api/chat/sessions')data={sessions:[{id:'s1',model:'alpha:sonnet'},{id:'s2',model:'alpha:sonnet'}]};
        else if(/^\/api\/chat\/sessions\/s[12]$/.test(path))data={session:{id:path.split('/').pop(),model:'alpha:sonnet'},messages:[],seq:0};
        return {ok:true,status:200,json:async()=>data};
      };
      sessionStorage.setItem('xc-token','offline-test');
      const root=document.createElement('main');document.body.replaceChildren(root);
      const view=await import('/static/''' + view + '''.js');
      window.unmount=view.mount(root);
    })()''')


def test_providers_search_saves_exact_default_only_after_enter(page):
    mount_view(page, 'providers')
    page.wait('!!document.querySelector("[role=combobox]")')
    search(page, 'beta sonnet')
    assert page.eval(PROVIDER_POSTS + '.length') == 0
    key(page, 'Enter')
    page.wait(PROVIDER_POSTS + '.length === 1')
    assert page.eval(PROVIDER_POSTS) == [{'path': '/api/providers/default', 'body': {'ref': 'beta:sonnet', 'role': 'main'}}]
    page.wait('document.querySelector(".xc-model-status").textContent.includes("Default set")')


def command(page, text):
    page.eval('(()=>{const input=document.querySelector(".xc-input");input.value=' + repr(text) + ';input.dispatchEvent(new Event("input"));document.querySelector(".xc-composer .xc-btnrow button").click()})()')


@pytest.mark.parametrize(('text', 'path', 'body'), [
    ('/model', '/api/chat/sessions/s1/model', {'model': 'beta:sonnet'}),
    ('/default', '/api/providers/default', {'ref': 'beta:sonnet', 'role': 'main'}),
])
def test_chat_search_preserves_thread_and_default_routes_and_returns_focus(page, text, path, body):
    mount_view(page, 'chat')
    page.wait('document.querySelectorAll(".xc-sess").length === 2')
    command(page, text)
    page.wait('!!document.querySelector("[role=combobox]")')
    assert page.eval('document.querySelector(".xc-model-note").textContent.includes("shared core")')
    assert page.eval('document.querySelector(".xc-model-note").textContent.includes("default for new threads")') == (text == '/default')
    search(page, 'beta sonnet')
    assert page.eval('posts.filter(p=>p.path.endsWith("/model")||p.path.endsWith("/default")).length') == 0
    key(page, 'Enter')
    page.wait('posts.some(p=>p.path===' + repr(path) + ')')
    assert page.eval('posts.filter(p=>p.path.endsWith("/model")||p.path.endsWith("/default"))') == [{'path': path, 'body': body}]
    page.wait('document.activeElement.classList.contains("xc-input")')


def test_chat_picker_stays_one_column_inside_the_grid_composer(page):
    mount_view(page, 'chat')
    page.wait('document.querySelectorAll(".xc-sess").length === 2')
    command(page, '/model')
    page.wait('!!document.querySelector("[role=combobox]") && document.querySelectorAll("[role=option]").length > 0')
    layout = page.eval('''(()=>{
      const picker=document.querySelector('.xc-composer .xc-search-model-picker');
      const box=e=>e.getBoundingClientRect();
      const field=box(picker.querySelector('[role=combobox]')), row=box(picker.querySelector(':scope > .xc-btnrow'));
      return {width:innerWidth, columns:getComputedStyle(picker).gridTemplateColumns.trim().split(/\\s+/).length,
              sameLeft:Math.abs(field.left-row.left)<1, rowBelow:row.top>=field.bottom};
    })()''')
    assert layout == {'width': 1440, 'columns': 1, 'sameLeft': True, 'rowBelow': True}


# Contrast as test_workspace_design.py measures it (WCAG ratio against the first opaque background), with the
# text's own opacity and its ancestors' opacity blended in, because the picker's text colour alone ignores them.
PICKER_TEXT_CONTRAST = r"""(()=>{
  const css=e=>getComputedStyle(e),rgb=value=>(value.match(/[\d.]+/g)||[]).map(Number);
  const background=e=>{for(let n=e;n;n=n.parentElement){const c=css(n).backgroundColor,a=rgb(c);if(a.length===3 || a[3]===1)return c;}return css(document.body).backgroundColor;};
  const luminance=color=>color.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
  const ratio=(a,b)=>{const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
  const shown=e=>{let alpha=rgb(css(e).color)[3]??1;for(let n=e;n;n=n.parentElement)alpha*=Number(css(n).opacity);
    const fg=rgb(css(e).color),bg=rgb(background(e));return fg.slice(0,3).map((v,i)=>alpha*v+(1-alpha)*bg[i]);};
  const picker=document.querySelector('.xc-composer .xc-model-picker');
  return Object.fromEntries(['.xc-model-status','.xc-model-note'].map(sel=>{const e=picker.querySelector(sel);
    return [sel,{text:e.textContent.length>0,ratio:Math.round(ratio(shown(e),rgb(background(e)))*100)/100}];}));
})()"""


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_chat_picker_status_and_note_text_are_readable_in_each_theme(page, theme):
    """The chat picker's status and note keep the 4.5:1 text contrast that test_workspace_design.py asks of #801's text."""
    mount_view(page, 'chat')
    page.wait('document.querySelectorAll(".xc-sess").length === 2')
    page.eval("(async()=>{(await import('/static/appearance.js')).applyAppearance('" + theme + "');})()")
    assert page.eval('document.documentElement.dataset.theme') == theme
    command(page, '/model')
    page.wait('!!document.querySelector("[role=combobox]") && document.querySelectorAll("[role=option]").length > 0')
    search(page, 'no such model')
    page.wait('document.querySelector(".xc-model-status").textContent.startsWith("No matching models")')
    measured = page.eval(PICKER_TEXT_CONTRAST)
    assert all(m['text'] for m in measured.values()), measured
    assert all(m['ratio'] >= 4.5 for m in measured.values()), measured


def test_chat_escape_and_old_picker_cannot_change_new_thread(page):
    mount_view(page, 'chat')
    page.wait('document.querySelectorAll(".xc-sess").length === 2')
    command(page, '/model')
    page.wait('!!document.querySelector("[role=combobox]")')
    search(page, 'beta')
    key(page, 'Escape')
    assert page.eval('document.querySelector(".xc-model-picker").hidden && document.activeElement.classList.contains("xc-input")')
    command(page, '/model')
    page.wait('!document.querySelector(".xc-model-picker").hidden')
    page.eval('window.oldSearch=document.querySelector("[role=combobox]");document.querySelectorAll(".xc-sess")[1].click()')
    page.eval('oldSearch.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",bubbles:true,cancelable:true}))')
    assert page.eval('posts.filter(p=>p.path.endsWith("/model")||p.path.endsWith("/default")).length') == 0


def test_loading_and_apply_error_keep_search_available_for_retry(page):
    page.eval('''(async()=>{
      const {createModelPicker}=await import('/static/model_picker.js');
      window.attempts=0;
      window.picker=createModelPicker({label:'Model',onApply:async()=>{if(++attempts===1)throw Error('Core refused this model');}});
      document.body.replaceChildren(picker.element);picker.focus();
    })()''')
    assert page.eval('document.querySelector("[role=status]").textContent.includes("Loading models") && document.querySelector(".xc-primary").disabled')
    search(page, 'beta')
    key(page, 'Enter')
    assert page.eval('attempts') == 0
    page.eval('picker.setRows([{route:"beta:sonnet",name:"Sonnet"}])')
    key(page, 'Enter')
    page.wait('document.querySelector("[role=status]").textContent === "Core refused this model"')
    assert page.eval('document.activeElement.value === "beta" && !document.activeElement.disabled')
    key(page, 'Enter')
    page.wait('attempts === 2')


def test_model_search_ignores_name_punctuation_and_prioritizes_exact_route(page):
    prepare(page)
    page.eval('picker.setRows([{route:"alpha:gpt-6-pro",name:"GPT 6 Pro"},{route:"beta:sonnet-4",name:"Claude Sonnet 4"},{route:"beta:gpt6",name:"GPT 6"}])')
    search(page, 'gpt6')
    assert page.eval('document.querySelectorAll("[role=option]").length') == 2
    search(page, 'sonnet4')
    key(page, 'Enter')
    page.wait('applied.length === 1')
    assert page.eval('applied') == ['beta:sonnet-4']
    search(page, 'beta:gpt6')
    key(page, 'Enter')
    page.wait('applied.length === 2')
    assert page.eval('applied')[-1] == 'beta:gpt6'


def test_providers_next_start_reply_is_not_shown_as_applied_now(page):
    mount_view(page, 'providers', applied='"next start"')
    page.wait('!!document.querySelector("[role=combobox]")')
    search(page, 'beta')
    key(page, 'Enter')
    page.wait('document.querySelector(".xc-model-status").textContent.includes("core will use it on next start")')
    assert page.eval(PROVIDER_POSTS) == [{'path': '/api/providers/default', 'body': {'ref': 'beta:sonnet', 'role': 'main'}}]


def mount_providers_with_model_reads(page, replies):
    """Mount the Providers view; each /api/providers/models read answers with the next reply in turn.

    A reply written as {held: reply} answers only when the test calls releaseHeld().
    """
    page.eval(r'''(async()=>{
      window.modelReplies=''' + replies + r'''; window.modelReads=0;
      window.fetch=async (path,opt={})=>{
        let data={};
        if(path.endsWith('/models')){
          data=modelReplies[Math.min(modelReads++,modelReplies.length-1)];
          if(data.held){const reply=data.held; await new Promise(r=>{window.releaseHeld=r;}); data=reply;}
        }
        else if(path==='/api/providers')data={providers:[{provider:'local',needs:'cli',ready:true}],ready:true};
        else if(path.endsWith('/test'))data={ok:true,latency_ms:1};
        return {ok:true,status:200,json:async()=>data};
      };
      sessionStorage.setItem('xc-token','offline-test');
      const root=document.createElement('main');document.body.replaceChildren(root);
      const view=await import('/static/providers.js');
      window.unmount=view.mount(root);
    })()''')


def click_button(page, text):
    page.eval('[...document.querySelectorAll("button")].find(b=>b.textContent===' + repr(text) + ').click()')


TRY_AGAIN = '[...document.querySelectorAll(".xc-prov-def button")].filter(b=>b.textContent==="Try again").length'
DOWN = '{models:[],available:[],error:"Exo core is not reachable.",error_class:"transport",retryable:true}'


def test_providers_model_list_failure_names_the_class_and_retries_only_a_transport_failure(page):
    """D-091 in the search picker: a refusal shows its sentence with no retry; a transport failure offers one."""
    refused = '{models:[],available:[],error:"The core refused this request.",error_class:"authority",retryable:false}'
    mount_providers_with_model_reads(page, '[' + refused + ']')
    page.wait('document.querySelector(".xc-model-status").textContent === "The core refused this request."')
    assert page.eval(TRY_AGAIN) == 0
    page.eval('unmount()')
    good = "{models:[{route:'alpha:sonnet',name:'Sonnet'}],available:[]}"
    mount_providers_with_model_reads(page, '[' + DOWN + ',' + good + ']')
    page.wait('document.querySelector(".xc-model-status").textContent === "Exo core is not reachable."')
    assert page.eval(TRY_AGAIN) == 1
    click_button(page, 'Try again')
    page.wait('document.querySelectorAll("[role=option]").length === 1')
    assert page.eval(TRY_AGAIN) == 0 and page.eval('modelReads') == 2


def test_providers_failed_reread_keeps_the_last_good_list(page):
    """D-091: a failed read after a good one keeps the list usable and says it is the last good read."""
    good = "{models:[{route:'alpha:sonnet',name:'Sonnet'}],available:[{route:'beta:sonnet',name:'Sonnet'}]}"
    mount_providers_with_model_reads(page, '[' + good + ',' + DOWN + ']')
    page.wait('document.querySelectorAll("[role=option]").length === 2')
    click_button(page, 'Test')   # a provider test reloads the page data, so the list is read again
    page.wait('!!document.querySelector(".xc-prov-def .xc-warn")')
    assert page.eval('modelReads') == 2
    assert page.eval('document.querySelector(".xc-prov-def .xc-warn").textContent') == (
        "Exo core is not reachable. This list is from the last good read.")
    assert page.eval('document.querySelectorAll("[role=option]").length') == 2 and page.eval(TRY_AGAIN) == 0


def test_providers_slow_failed_read_cannot_overwrite_a_newer_good_list(page):
    """A failed model read that answers after a newer good read changes nothing: no last-good warning appears."""
    good = "{models:[{route:'alpha:sonnet',name:'Sonnet'}],available:[{route:'beta:sonnet',name:'Sonnet'}]}"
    mount_providers_with_model_reads(page, '[' + good + ',{held:' + DOWN + '},' + good + ']')
    page.wait('document.querySelectorAll("[role=option]").length === 2')
    click_button(page, 'Test')   # read 2 is held, and fails when released
    page.wait('modelReads === 2 && typeof releaseHeld === "function"')
    click_button(page, 'Test')   # read 3 is newer and answers at once
    page.wait('modelReads === 3 && document.querySelector(".xc-prov-res").textContent.startsWith("Test ok")')
    page.eval('new Promise(r=>setTimeout(r,0))')
    assert page.eval('!!document.querySelector(".xc-prov-def .xc-warn")') is False
    # Release the stale failure, then redraw at once: a provider test draws "Testing..." before it reads again.
    shown = page.eval('''(async()=>{
      releaseHeld(); await new Promise(r=>setTimeout(r,0));
      [...document.querySelectorAll("button")].find(b=>b.textContent==="Test").click();
      return [!!document.querySelector(".xc-prov-def .xc-warn"), document.querySelectorAll("[role=option]").length,
              document.querySelector(".xc-prov-res").textContent];
    })()''')
    assert shown == [False, 2, 'Testing...']
