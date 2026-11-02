"""A failed refresh keeps the picker usable and lets the operator retry in place."""
import asyncio
import importlib.util
import threading
import time

import pytest

from browser import Browser, Served, find_chrome
from test_layout_web import ThreadSrc
from exo_command import providers

# The fork draws the default model with its search picker (model_picker.js), not a <select>: the model control is
# the picker's search field, the chosen route is its active option, and a route is listed as an option's route text.
SELECT = "document.querySelector('.xc-prov-def .xc-model-search')"
VALUE = "document.querySelector('.xc-prov-def [role=option][aria-selected=\"true\"] .xc-model-route')?.textContent"


def listed(route):
    return f"[...document.querySelectorAll('.xc-prov-def .xc-model-route')].some(e => e.textContent === '{route}')"


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('retryable', [True, False])
def test_cached_model_error_has_retry_only_when_allowed(monkeypatch, retryable):
    reads = []
    failing = [False]

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, {'providers': [{'provider': 'demo', 'needs': 'none', 'ready': True}], 'ready': True, 'store': 'environment'}
        if path == '/api/providers/models':
            reads.append(path)
            if failing[0]:
                return 200, {'error': 'Synthetic model-list failure', 'retryable': retryable, 'error_class': 'transport' if retryable else 'authority'}
            return 200, {'models': [{'route': 'demo:first'}], 'available': [{'route': 'demo:recovered'}] if len(reads) > 2 else []}
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            b.wait(f"{VALUE} === 'demo:first'")
            failing[0] = True
            b.eval("[...document.querySelectorAll('button')].find(b=>b.textContent==='Test').click()")
            b.wait("document.body.textContent.includes('This list is from the last good read.')")
            assert b.eval(VALUE) == 'demo:first'
            assert b.eval("[...document.querySelectorAll('button')].filter(b=>b.textContent==='Try again').length") == int(retryable)
            if retryable:
                failing[0] = False
                before = len(reads)
                b.eval("[...document.querySelectorAll('button')].find(b=>b.textContent==='Try again').click()")
                b.wait(listed('demo:recovered'))
                assert not b.eval("document.body.textContent.includes('This list is from the last good read.')")
                b.wait(f"{VALUE} === 'demo:first'")
                assert len(reads) == before + 1
    finally:
        srv.close()


PROVIDERS = {'providers': [{'provider': 'demo', 'needs': 'none', 'ready': True}], 'ready': True, 'store': 'environment'}
MODEL_REPLIES = {
    'list': {'models': [{'route': 'demo:first'}], 'available': []},
    'succeeds': {'models': [{'route': 'demo:first'}], 'available': [{'route': 'demo:recovered'}]},
    'fails': {'error': 'Synthetic model-list failure', 'retryable': True, 'error_class': 'transport'},
    'refused': {'error': 'Synthetic refusal', 'retryable': False, 'error_class': 'authority'},
    'empty': {'models': [], 'available': []},
}
RETRY = "[...document.querySelectorAll('button')].find(b=>b.textContent==='Try again')"
# For each outcome of the retry: what shows the reply was drawn, and what should then hold focus.
# The fork's picker stays drawn with an empty list ("No models listed") and with a refusal and no list (the refusal
# in its status line), so in both cases its search field is the model control that takes focus.
DRAWN = {
    'succeeds': listed('demo:recovered'),
    'fails': f"(() => {{ const t = {RETRY}; return !!t && t !== window.oldRetry; }})()",
    'refused': "document.body.textContent.includes('Synthetic refusal')",
    'empty': "!!document.querySelector('.xc-prov-def .xc-model-status')?.textContent.startsWith('No models listed')",
}
FOCUSED = {
    'succeeds': SELECT,
    'fails': RETRY,
    'refused': SELECT,
    'empty': SELECT,
}


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('cached,outcome', [
    (True, 'succeeds'), (True, 'fails'), (True, 'refused'), (True, 'empty'),
    (False, 'succeeds'), (False, 'fails'), (False, 'refused'),
], ids=lambda v: {True: 'cached-list', False: 'no-list'}.get(v, 'retry-' + str(v)))
def test_keyboard_retry_keeps_focus_in_the_picker(monkeypatch, cached, outcome):
    """Space on Try again redraws the picker. Focus lands on Try again when it is drawn again, else on the model
    search, which the fork's picker always draws (exo's refusal-message and workspace fallbacks are not reached)."""
    reads = []
    reply = ['list' if cached else 'fails']

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, PROVIDERS
        if path == '/api/providers/models':
            reads.append(path)
            return 200, MODEL_REPLIES[reply[0]]
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            if cached:
                b.wait(f"{VALUE} === 'demo:first'")
                reply[0] = 'fails'
                b.eval("[...document.querySelectorAll('button')].find(b=>b.textContent==='Test').click()")
            b.wait(f"!!{RETRY}")
            b.eval(f"window.oldRetry = {RETRY}; window.oldRetry.focus()")
            assert b.eval("document.activeElement === window.oldRetry")
            reply[0] = outcome
            before = len(reads)
            b.press(' ', 'Space', 32)
            b.wait(DRAWN[outcome])
            want = FOCUSED[outcome]
            # The tag name of whatever holds focus instead, so a failure says where focus went (BODY when lost).
            assert b.eval(f"document.activeElement === {want} || document.activeElement.tagName") is True
            assert len(reads) == before + 1
    finally:
        srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
def test_retry_leaves_focus_moved_away_alone(monkeypatch):
    """Focus the person moves out of the panel while a retry runs stays there when the reply is drawn."""
    reads = []
    release = threading.Event()

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, PROVIDERS
        if path == '/api/providers/models':
            reads.append(path)
            if len(reads) > 1:   # hold the retry until the test has moved focus
                for _ in range(500):
                    if release.is_set():
                        break
                    await asyncio.sleep(0.02)
            return 200, MODEL_REPLIES['fails']
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            b.wait(f"!!{RETRY}")
            b.eval(f"window.oldRetry = {RETRY}; window.oldRetry.focus()")
            b.press(' ', 'Space', 32)
            end = time.monotonic() + 10
            while len(reads) < 2 and time.monotonic() < end:
                time.sleep(0.02)
            assert len(reads) == 2
            b.eval("document.getElementById('xc-skip').focus()")
            release.set()
            b.wait(DRAWN['fails'])
            assert b.eval("document.activeElement.id") == 'xc-skip'
    finally:
        release.set()
        srv.close()


TEST = "[...document.querySelectorAll('button')].find(b=>b.textContent==='Test')"
# Two rows with a Test button each, so focus has to come back to the row it was in, not to the first Test.
# The second row takes a key, so it also has Save and Remove: focus has to come back to Test, not to Save.
TWO_ROWS = {'providers': [{'provider': 'demo', 'needs': 'none', 'ready': True},
                          {'provider': 'spare', 'needs': 'key', 'key': 'found', 'ready': True}],
            'ready': True, 'store': 'environment'}
SPARE_TEST = ("[...[...document.querySelectorAll('.xc-prow')].find(r => r.querySelector('.xc-prow-name').textContent"
              " === 'spare').querySelectorAll('button')].find(b => b.textContent === 'Test')")
ADD_CUSTOM = "[...document.querySelectorAll('button')].find(b=>b.textContent==='Add custom provider')"
MOVED_TO = {'test': SPARE_TEST, 'select': SELECT, 'add-custom': ADD_CUSTOM}
# Where focus is, as tag and label, so a failure names it ("BUTTON:Try again", "INPUT:Default model search", "BODY:...").
WHERE = "(e => e.tagName + ':' + (e.getAttribute('aria-label') || e.textContent))(document.activeElement)"


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('outcome', ['fails', 'succeeds'])
@pytest.mark.parametrize('moved', ['test', 'select', 'add-custom'])
def test_held_retry_keeps_focus_moved_inside_the_panel(monkeypatch, moved, outcome):
    """Focus the person moves to another Providers control while a retry runs is on that control again once the
    reply has redrawn the panel (#1014). The reply replaces the control, so focus goes to its new copy. The
    controls are a provider's Test button, the model search and the custom providers' Add button."""
    reads = []
    reply = ['list']
    hold, release = threading.Event(), threading.Event()

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, TWO_ROWS
        if path == '/api/providers/models':
            reads.append(path)
            if hold.is_set():   # hold the retry until the test has moved focus
                for _ in range(500):
                    if release.is_set():
                        break
                    await asyncio.sleep(0.02)
            return 200, MODEL_REPLIES[reply[0]]
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            b.wait(f"{VALUE} === 'demo:first'")
            reply[0] = 'fails'
            b.eval(f"{TEST}.click()")
            b.wait(f"!!{RETRY}")
            b.eval(f"window.oldRetry = {RETRY}; window.oldRetry.focus()")
            hold.set()
            reply[0] = outcome
            before = len(reads)
            b.press(' ', 'Space', 32)
            end = time.monotonic() + 10
            while len(reads) == before and time.monotonic() < end:
                time.sleep(0.02)
            assert len(reads) == before + 1
            b.eval(f"window.moved = {MOVED_TO[moved]}; window.moved.focus()")
            assert b.eval("document.activeElement === window.moved")
            release.set()
            b.wait(DRAWN[outcome])
            assert b.eval("window.moved.isConnected") is False   # the reply redrew the control
            assert b.eval(f"document.activeElement === {MOVED_TO[moved]} || {WHERE}") is True
            assert b.eval(VALUE) == 'demo:first'
    finally:
        release.set()
        srv.close()


STATUS = "document.querySelector('.xc-prov-def .xc-model-status')?.textContent"
WARN = "document.querySelector('.xc-prov-def .xc-warn')?.textContent"
OPTIONS = "[...document.querySelectorAll('.xc-prov-def [role=option] .xc-model-route')].map(e => e.textContent)"


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('outcome', ['succeeds', 'fails', 'refused'])
@pytest.mark.parametrize('cached', [True, False], ids=['cached-list', 'no-list'])
def test_held_retry_reply_reaches_a_loading_picker_being_searched(monkeypatch, cached, outcome):
    """Fork: a model search with focus stops a redraw, but not of a picker drawn while a retry loads. The reply is
    drawn, and the new picker's search keeps the focus and the text typed while it loaded, filtering the new list.
    A failed reply still says why: beside a cached list in the warning, else in the picker's status line, which the
    carried text must not clear."""
    reads = []
    reply = ['list' if cached else 'fails']
    hold, release = threading.Event(), threading.Event()

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, PROVIDERS
        if path == '/api/providers/models':
            reads.append(path)
            if hold.is_set():
                for _ in range(500):
                    if release.is_set():
                        break
                    await asyncio.sleep(0.02)
            return 200, MODEL_REPLIES[reply[0]]
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            if cached:
                b.wait(f"{VALUE} === 'demo:first'")
                reply[0] = 'fails'
                b.eval(f"{TEST}.click()")
            b.wait(f"!!{RETRY}")
            hold.set()
            reply[0] = outcome
            before = len(reads)
            b.eval(f"{RETRY}.click()")
            end = time.monotonic() + 10
            while len(reads) == before and time.monotonic() < end:
                time.sleep(0.02)
            assert len(reads) == before + 1
            assert b.eval(STATUS) == 'Loading models…'
            b.type('.xc-prov-def .xc-model-search', 'recov')
            b.eval(f"window.moved = {SELECT}")
            release.set()
            b.wait("!window.moved.isConnected")   # the reply redrew the picker
            assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
            assert b.eval(f"{SELECT}.value") == 'recov'
            assert b.eval(OPTIONS) == (['demo:recovered'] if outcome == 'succeeds' else [])
            if outcome != 'succeeds':
                reason = MODEL_REPLIES[outcome]['error']
                if cached:
                    assert b.eval(WARN) == reason + ' This list is from the last good read.'
                else:
                    assert b.eval(STATUS) == reason
            assert b.eval(f"!!{RETRY}") is (outcome == 'fails')
    finally:
        release.set()
        srv.close()


async def opened(gate):
    """Hold a request on the server's loop until the test opens its gate (at most 10 s). None does not hold."""
    for _ in range(500):
        if gate is None or gate.is_set():
            return
        await asyncio.sleep(0.02)


def arrived(seen, path, count):
    """Wait until the server has seen `count` requests for `path`."""
    end = time.monotonic() + 10
    while seen.count(path) < count and time.monotonic() < end:
        time.sleep(0.02)
    assert seen.count(path) == count


# Counts the model-list replies the page has read. The count goes up one task after a reply is read, so the code
# that awaited that reply has run by then, whether it drew anything or not.
COUNT_REPLIES = ("(() => { window.replies = 0; const json = Response.prototype.json;"
                 " Response.prototype.json = async function () { const d = await json.call(this);"
                 " if (this.url.includes('/api/providers/models')) setTimeout(() => window.replies++); return d; }; })()")
# The page's model-list reads skip the HTTP cache, for tests that hold one while a newer one starts. Chrome's cache
# lock makes a second GET for a URL wait for an unanswered first one. Chromium 141 skips that after exo's no-store
# replies, but newer Chrome (156 on CI) waits even then, so the held read would block the newer one the test waits
# for. The page is fine with that: the newer read then lands after the held one.
NO_STORE = ("(() => { const fetch = window.fetch.bind(window); window.fetch = (url, opt) =>"
            " fetch(url, String(url).includes('/api/providers/models') ? {...opt, cache: 'no-store'} : opt); })()")
CUSTOM_FORM = "document.querySelector('.xc-custom-form')"


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('focus', ['model-search', 'key'])
def test_custom_provider_save_is_drawn_while_a_field_holds_the_panel(monkeypatch, focus):
    """Fork: the panel is not redrawn while the model search has focus or a provider key is being typed. A custom
    provider saved meanwhile still closes its form and shows the saved entry when the reload after the save lands,
    because the custom providers section is redrawn on its own. The form used to stay open after its entry was
    cleared, and the next Save threw before it sent anything."""
    reads, posts, saved = [], [], []
    hold, release = threading.Event(), threading.Event()

    async def handle(centre, method, path, body, router_factory=None):
        if path == '/api/providers':
            return 200, TWO_ROWS
        if path == '/api/providers/custom':
            if method == 'POST':
                posts.append(body)
                saved[:] = [{k: body[k] for k in ('name', 'endpoint', 'protocol', 'auth', 'model')}]
                return 200, {'provider': 'custom-' + body['name'], 'ok': True}
            return 200, {'providers': list(saved)}
        if path == '/api/providers/models':
            reads.append(path)
            if hold.is_set():   # hold the reload after the save until the test has moved focus
                await opened(release)
            return 200, MODEL_REPLIES['list']
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            b.wait(f"{VALUE} === 'demo:first'")
            b.eval("window.rejections = []; addEventListener('unhandledrejection', e => rejections.push(String(e.reason)))")
            b.eval(f"{ADD_CUSTOM}.click()")
            b.type('[aria-label="Provider name"]', 'demo')
            b.type('[aria-label="Base URL"]', 'https://example.test/v1')
            b.type('[aria-label="Model ID"]', 'model-one')
            b.eval(COUNT_REPLIES)
            hold.set()
            before = len(reads)
            b.eval(f"{CUSTOM_FORM}.requestSubmit()")
            arrived(reads, '/api/providers/models', before + 1)
            assert len(posts) == 1
            if focus == 'model-search':
                b.eval(f"{SELECT}.focus()")
            else:
                b.type('[aria-label="API key for spare"]', 'synthetic-not-a-key')
            b.eval("window.kept = document.activeElement")
            release.set()
            b.wait("window.replies === 1")
            assert b.eval(f"!!{CUSTOM_FORM}") is False
            assert b.eval("document.body.textContent.includes('Saved custom-demo. Restart the core to use these settings.')")
            assert b.eval("[...document.querySelectorAll('button')].some(b => b.textContent === 'Edit demo')")
            assert b.eval("document.activeElement === window.kept && window.kept.isConnected") is True
            if focus == 'key':
                assert b.eval("window.kept.value") == 'synthetic-not-a-key'
            assert b.eval("window.rejections") == []
            assert len(posts) == 1
    finally:
        release.set()
        srv.close()


NEWEST = {'models': [{'route': 'demo:first'}], 'available': [{'route': 'demo:newest'}]}
# Which click starts first, which request of the newer load is held, and which reply lands first.
SUPERSEDED = {
    'load-answers-first': ('retry', 'models', ['load', 'retry']),
    'retry-answers-first': ('retry', 'models', ['retry', 'load']),
    'retry-answers-before-the-load-reads-models': ('retry', 'providers', ['retry', 'load']),
    'load-started-first': ('test', 'providers', ['load', 'retry']),
}


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('case', list(SUPERSEDED))
def test_a_retry_a_newer_load_supersedes_neither_draws_nor_moves_focus(monkeypatch, case):
    """A provider's Test starts a load once its request is answered, so a Test answered while a retry waits
    supersedes the retry (D-091, fork amendment of 2026-11-01). The retry's reply must then neither draw nor move
    focus, whichever reply lands first, and the panel ends on the newest load's list. Focus stays where the newer
    load left it.

    The retry used to draw and move focus to the model search, and a search with focus then kept the newest list
    from being drawn. The last case starts the load just before the retry: the load reads the models after the retry
    does, so the retry's reply is the stale one there too."""
    seen, models_plan, providers_plan = [], [], []
    retry_gate, load_gate = threading.Event(), threading.Event()
    first, held, opens = SUPERSEDED[case]

    async def handle(centre, method, path, body, router_factory=None):
        seen.append(path)
        if path == '/api/providers':
            await opened(providers_plan.pop(0) if providers_plan else None)
            return 200, PROVIDERS
        if path == '/api/providers/models':
            reply, gate = models_plan.pop(0) if models_plan else ('list', None)
            await opened(gate)
            return 200, NEWEST if reply == 'newest' else MODEL_REPLIES[reply]
        return 200, {'ok': True}

    monkeypatch.setattr(providers, 'handle', handle)
    srv = Served(ThreadSrc(pairs=0))
    try:
        with Browser() as b:
            b.goto(srv.url('providers'))
            b.eval(NO_STORE)
            b.wait(f"{VALUE} === 'demo:first'")
            models_plan.append(('fails', None))
            b.eval(f"{TEST}.click()")
            b.wait(f"!!{RETRY}")
            b.eval(COUNT_REPLIES)
            # The retry reads the models first in every case. The newer load reads them second.
            models_plan[:] = [('succeeds', retry_gate), ('newest', load_gate if held == 'models' else None)]
            if held == 'providers':
                providers_plan.append(load_gate)
            for click in (['test', 'retry'] if first == 'test' else ['retry', 'test']):
                # Each click's request is held where its gate stands, so wait until it got there.
                path = '/api/providers/models' if click == 'retry' or held == 'models' else '/api/providers'
                count = seen.count(path) + 1
                b.eval(f"{RETRY if click == 'retry' else TEST}.click()")
                arrived(seen, path, count)
            for n, gate in enumerate(opens, 1):
                (retry_gate if gate == 'retry' else load_gate).set()
                b.wait(f"window.replies === {n}")
                if gate == 'load':
                    b.eval(f"window.drawn = {SELECT}")
            assert b.eval(OPTIONS) == ['demo:first', 'demo:newest']
            assert b.eval("document.activeElement === document.body || " + WHERE) is True
            assert b.eval("window.drawn.isConnected") is True   # nothing redrew the picker after the newest load
    finally:
        retry_gate.set()
        load_gate.set()
        srv.close()


MODELS = '/api/providers/models'
TEST_PATH = '/api/providers/demo/test'
# The demo row's result line ("Testing...", "Test ok in 2 ms.").
DEMO_RESULT = "document.querySelector('.xc-prow .xc-prov-res')?.textContent"
KEY_FIELD = '[aria-label="API key for spare"]'
CUSTOM_KEY = '[aria-label="Custom provider API key"]'
NAME_FIELD = "document.querySelector('.xc-custom-form [aria-label=\"Provider name\"]')"
CANCEL = "[...document.querySelectorAll('.xc-custom-form button')].find(b => b.textContent === 'Cancel')"
REJECTIONS = "window.rejections = []; addEventListener('unhandledrejection', e => rejections.push(String(e.reason)))"
SAVED = {'name': 'demo', 'endpoint': 'https://example.test/v1', 'protocol': 'openai', 'auth': 'key', 'model': 'model-one'}


class Planned:
    """Serves the provider routes from plans the test fills in. `models` holds (reply, gate) pairs for the next
    model-list reads. `providers` and `tests` hold gates for the next provider reads and demo Tests. A gate holds its
    request until the test opens it, and None does not hold. The Nth Test answers "Test ok in N ms.", so a result is
    told from an earlier one. A custom provider saved with POST is listed by the next read."""

    def __init__(self, monkeypatch, rows=PROVIDERS, saved=()):
        self.seen, self.models, self.providers, self.tests, self.saved = [], [], [], [], list(saved)
        self.tested = 0

        async def handle(centre, method, path, body, router_factory=None):
            self.seen.append(path)
            if path == '/api/providers':
                await opened(self.providers.pop(0) if self.providers else None)
                return 200, rows
            if path == MODELS:
                reply, gate = self.models.pop(0) if self.models else ('list', None)
                await opened(gate)
                return 200, NEWEST if reply == 'newest' else MODEL_REPLIES[reply]
            if path == TEST_PATH:
                await opened(self.tests.pop(0) if self.tests else None)
                self.tested += 1
                return 200, {'ok': True, 'latency_ms': self.tested}
            if path == '/api/providers/custom':
                if method == 'POST':
                    self.saved[:] = [{k: body[k] for k in ('name', 'endpoint', 'protocol', 'auth', 'model')}]
                    return 200, {'provider': 'custom-' + body['name'], 'ok': True}
                return 200, {'providers': list(self.saved)}
            return 200, {'ok': True}

        monkeypatch.setattr(providers, 'handle', handle)
        self.srv = Served(ThreadSrc(pairs=0))


def open_at_a_failed_list(b, s, cached):
    """Open Providers at a failed model list with Try again, beside a cached list or with none. From then on the page
    counts model-list replies and records unhandled rejections."""
    if not cached:
        s.models.append(('fails', None))
    b.goto(s.srv.url('providers'))
    if cached:
        b.wait(f"{VALUE} === 'demo:first'")
        s.models.append(('fails', None))
        b.eval(f"{TEST}.click()")
    b.wait(f"!!{RETRY}")
    b.eval(REJECTIONS)
    b.eval(COUNT_REPLIES)


def click_at(b, el, point=None):
    """Press and release the mouse as a person clicks (pointerdown, focus, click) at `point`, a script for [x, y],
    by default the middle of `el`. The press has to land on `el` itself."""
    b.eval(f"{el}.scrollIntoView({{block: 'center'}})")
    x, y = b.eval(point or f"(r => [r.x + r.width / 2, r.y + r.height / 2])({el}.getBoundingClientRect())")
    assert b.eval(f"document.elementFromPoint({x}, {y}) === {el}") is True
    for kind in ('mousePressed', 'mouseReleased'):
        b.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left', clickCount=1)


# How a Test's load meets a retry whose reply is still the newest when it lands, so the retry draws and moves focus.
GIVES_WAY = {
    # Test is clicked while the retry waits and answers after the retry, so its load starts after the retry drew.
    'test-answers-after-the-retry': 'tests',
    # A Test's load waits on the provider list when Try again is clicked, so it reads the models after the retry.
    'load-reads-the-list-after-the-retry': 'providers',
}


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('case', list(GIVES_WAY))
@pytest.mark.parametrize('cached', [False, True], ids=['no-list', 'cached-list'])
def test_a_search_the_retry_focused_does_not_hold_back_a_later_load(monkeypatch, cached, case):
    """The retry's reply draws and moves focus to the model search, the fork's model control (#932, #1092). The
    person has not used that search, so it does not hold back the Test's result or the load after it, and that redraw
    puts focus on the new search. The search used to hold back every redraw, so the panel kept the retry's list and
    "Testing..." until something redrew it after focus had left the search."""
    s = Planned(monkeypatch)
    retry_gate, gate = threading.Event(), threading.Event()
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, cached)
            if GIVES_WAY[case] == 'tests':
                s.models[:] = [('succeeds', retry_gate), ('newest', None)]
                s.tests.append(gate)
                count = s.seen.count(MODELS) + 1
                b.eval(f"{RETRY}.click()")
                arrived(s.seen, MODELS, count)
                count = s.seen.count(TEST_PATH) + 1
                b.eval(f"{TEST}.click()")
                arrived(s.seen, TEST_PATH, count)
                retry_gate.set()
            else:
                s.providers.append(gate)
                count = s.seen.count('/api/providers') + 1
                b.eval(f"{TEST}.click()")
                arrived(s.seen, '/api/providers', count)
                s.models[:] = [('succeeds', None), ('newest', None)]
                b.eval(f"{RETRY}.click()")
            b.wait("window.replies === 1")
            assert b.eval(OPTIONS) == ['demo:first', 'demo:recovered']   # the retry's reply was drawn
            assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
            b.eval(f"window.placed = {SELECT}")
            gate.set()
            b.wait("window.replies === 2")
            assert b.eval(OPTIONS) == ['demo:first', 'demo:newest']
            assert b.eval(DEMO_RESULT) == f"Test ok in {s.tested} ms."
            assert b.eval("window.placed.isConnected") is False
            assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
            assert b.eval("window.rejections") == []
    finally:
        retry_gate.set()
        gate.set()
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('use', ['types', 'arrow-key', 'click'])
def test_a_search_the_retry_focused_holds_the_panel_once_used(monkeypatch, use):
    """The search the retry moved focus to is the person's once they type in it, press a key in it or click it. Then
    it holds back redraws like any model search with focus, so a Test's load leaves that picker, its text and its
    chosen route as they are."""
    s = Planned(monkeypatch)
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, False)
            s.models[:] = [('succeeds', None), ('newest', None)]
            b.eval(f"{RETRY}.click()")
            b.wait("window.replies === 1")
            assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
            if use == 'types':
                b.type('.xc-prov-def .xc-model-search', 'rec')
            elif use == 'arrow-key':
                b.press('ArrowDown', 'ArrowDown', 40)
            else:
                click_at(b, SELECT)
            b.eval(f"window.used = {SELECT}; {TEST}.click()")
            b.wait("window.replies === 2")
            assert b.eval(f"window.used === {SELECT} && document.activeElement === window.used") is True
            assert b.eval(OPTIONS) == (['demo:recovered'] if use == 'types' else ['demo:first', 'demo:recovered'])
            assert b.eval(VALUE) == ('demo:first' if use == 'click' else 'demo:recovered')
            assert b.eval("window.rejections") == []
    finally:
        s.srv.close()


NOTE = "document.querySelector('.xc-prov-def .xc-model-note')"
LABEL = "document.querySelector('.xc-prov-def .xc-search-model-picker label')"
# The middle of the label's own text ("Default model"), beside the search field it holds.
LABEL_TEXT = ("(() => { const r = document.createRange(); r.selectNodeContents(" + LABEL + ".firstChild);"
              " const b = r.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()")
# What the page sees when the person switches to another window and back: a blur on the field with focus while the
# page has none, then a focus on that field, which kept focus all along. The test fires both events itself and has
# the page report no focus during the blur, so it does not depend on how a headless browser handles its windows.
OTHER_WINDOW = ("(f => { document.hasFocus = () => false; f.dispatchEvent(new FocusEvent('blur'));"
                " delete document.hasFocus; f.dispatchEvent(new FocusEvent('focus')); })(document.activeElement)")


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('back', ['tab', 'label', 'other-window'])
def test_a_search_the_retry_focused_is_the_persons_once_focus_leaves_it(monkeypatch, back):
    """The search the retry moved focus to is also the person's once focus leaves it for another part of the page.
    When they come back to it with Tab, or with a press on its "Default model" label, it holds back a Test's load,
    though neither sends the search a keydown or a pointerdown. A switch to another window and back leaves it the retry's, so
    the Test's load is drawn and moves focus to the new search."""
    s = Planned(monkeypatch)
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, False)
            # The page counts as focused whatever the state of its headless window, so a focus move in it fires blur.
            b.call('Emulation.setFocusEmulationEnabled', enabled=True)
            s.models[:] = [('succeeds', None), ('newest', None)]
            b.eval(f"{RETRY}.click()")
            b.wait("window.replies === 1")
            b.eval(f"window.search = {SELECT}")
            assert b.eval(f"document.activeElement === window.search || {WHERE}") is True
            if back == 'other-window':
                b.eval(OTHER_WINDOW)
            else:
                click_at(b, NOTE)
                assert b.eval("document.activeElement !== window.search") is True
                if back == 'tab':
                    for _ in range(20):   # Tab on from where the press left focus until the search has it again
                        b.press('Tab', 'Tab', 9)
                        if b.eval("document.activeElement === window.search"):
                            break
                else:
                    click_at(b, LABEL, LABEL_TEXT)
            assert b.eval(f"document.activeElement === window.search || {WHERE}") is True
            b.eval(f"{TEST}.click()")
            b.wait("window.replies === 2")
            if back == 'other-window':
                assert b.eval("window.search.isConnected") is False
                assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
                assert b.eval(OPTIONS) == ['demo:first', 'demo:newest']
            else:
                assert b.eval("window.search.isConnected && document.activeElement === window.search") is True
                assert b.eval(OPTIONS) == ['demo:first', 'demo:recovered']
            assert b.eval("window.rejections") == []
    finally:
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
def test_a_search_typed_in_while_loading_holds_the_panel_after_the_reply(monkeypatch):
    """Text typed into the loading picker's search while a retry waits makes that search the person's. The reply's
    picker takes the text and the focus, and its search is not placed, as one the retry moved focus to would be. So
    it holds back a Test's load, and the list stays filtered by the text."""
    s = Planned(monkeypatch)
    retry_gate = threading.Event()
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, False)
            s.models[:] = [('succeeds', retry_gate), ('newest', None)]
            count = s.seen.count(MODELS) + 1
            b.eval(f"{RETRY}.click()")
            arrived(s.seen, MODELS, count)
            b.type('.xc-prov-def .xc-model-search', 'rec')
            retry_gate.set()
            b.wait("window.replies === 1")
            b.eval(f"window.typed = {SELECT}")
            assert b.eval("document.activeElement === window.typed && window.typed.value") == 'rec'
            assert b.eval(OPTIONS) == ['demo:recovered']
            b.eval(f"{TEST}.click()")
            b.wait("window.replies === 2")
            assert b.eval("window.typed.isConnected && document.activeElement === window.typed") is True
            assert b.eval(OPTIONS) == ['demo:recovered']
            assert b.eval("window.rejections") == []
    finally:
        retry_gate.set()
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('focus', ['key', 'model-search'])
def test_custom_form_survives_a_reload_while_another_field_holds_the_panel(monkeypatch, focus):
    """Fork: while a provider key with text or the loaded model search holds the panel, the custom providers section
    is redrawn only for a save, Add, Edit or Cancel. A Test's reload leaves an open form alone: the same node, the
    fields filled in and the key typed into it."""
    s = Planned(monkeypatch, TWO_ROWS)
    try:
        with Browser() as b:
            b.goto(s.srv.url('providers'))
            b.wait(f"{VALUE} === 'demo:first'")
            b.eval(COUNT_REPLIES)
            b.eval(f"{ADD_CUSTOM}.click()")
            b.type('[aria-label="Provider name"]', 'demo')
            b.type('[aria-label="Base URL"]', 'https://example.test/v1')
            b.type('[aria-label="Model ID"]', 'model-one')
            b.type(CUSTOM_KEY, 'custom-synthetic-value')
            if focus == 'key':
                b.type(KEY_FIELD, 'synthetic-not-a-key')
            else:
                b.eval(f"{SELECT}.focus()")
            b.eval(f"window.form = {CUSTOM_FORM}; window.kept = document.activeElement; {TEST}.click()")
            b.wait("window.replies === 1")
            assert b.eval(f"{CUSTOM_FORM} === window.form") is True
            assert b.eval("[...window.form.querySelectorAll('input')].map(e => e.value)") == [
                'demo', 'https://example.test/v1', 'model-one', 'custom-synthetic-value']
            assert b.eval("document.activeElement === window.kept && window.kept.isConnected") is True
    finally:
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('focus', ['key', 'model-search'])
def test_add_and_edit_open_the_custom_form_while_a_field_holds_the_panel(monkeypatch, focus):
    """Fork: Add custom provider, Edit and Cancel redraw the custom providers section even while a provider key with
    text or the model search holds the rest of the panel. A click that leaves focus where it was (Safari's buttons, a
    script) still opens and closes the form, and focus stays on that field."""
    s = Planned(monkeypatch, TWO_ROWS, saved=[SAVED])
    try:
        with Browser() as b:
            b.goto(s.srv.url('providers'))
            b.wait(f"{VALUE} === 'demo:first'")
            if focus == 'key':
                b.type(KEY_FIELD, 'synthetic-not-a-key')
            else:
                b.eval(f"{SELECT}.focus()")
            b.eval("window.kept = document.activeElement")
            for button, name, disabled in ((ADD_CUSTOM, '', False),
                                           ("[...document.querySelectorAll('button')].find(b => b.textContent === 'Edit demo')", 'demo', True)):
                b.eval(f"{button}.click()")
                assert b.eval(f"[{NAME_FIELD}?.value, {NAME_FIELD}?.disabled]") == [name, disabled]
                b.eval(f"{CANCEL}.click()")
                assert b.eval(f"!{CUSTOM_FORM} && !!{ADD_CUSTOM}") is True
                assert b.eval("document.activeElement === window.kept && window.kept.isConnected") is True
            if focus == 'key':
                assert b.eval("window.kept.value") == 'synthetic-not-a-key'
    finally:
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
@pytest.mark.parametrize('cached', [False, True], ids=['no-list', 'cached-list'])
def test_a_newer_load_over_a_searched_loading_picker_keeps_the_search(monkeypatch, cached):
    """Text typed into the loading picker's search while a retry waits, then a Test whose load overtakes the retry.
    That load replaces the loading picker, and the new picker's search takes the text and the focus. The retry's
    reply, stale by then, changes nothing, so it cannot put focus back: the load's draw has to."""
    s = Planned(monkeypatch)
    retry_gate = threading.Event()
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, cached)
            b.eval(NO_STORE)
            s.models[:] = [('succeeds', retry_gate), ('newest', None)]
            count = s.seen.count(MODELS) + 1
            b.eval(f"{RETRY}.click()")
            arrived(s.seen, MODELS, count)
            b.type('.xc-prov-def .xc-model-search', 'new')
            b.eval(f"window.typed = {SELECT}; {TEST}.click()")
            b.wait("window.replies === 1")
            assert b.eval("window.typed.isConnected") is False
            assert b.eval(f"document.activeElement === {SELECT} || {WHERE}") is True
            assert b.eval(f"{SELECT}.value") == 'new'
            assert b.eval(OPTIONS) == ['demo:newest']
            assert b.eval(DEMO_RESULT) == f"Test ok in {s.tested} ms."
            b.eval(f"window.drawn = {SELECT}")
            retry_gate.set()
            b.wait("window.replies === 2")
            assert b.eval("window.drawn.isConnected && document.activeElement === window.drawn") is True
            assert b.eval(OPTIONS) == ['demo:newest']
            assert b.eval("window.rejections") == []
    finally:
        retry_gate.set()
        s.srv.close()


@pytest.mark.skipif(not find_chrome() or not importlib.util.find_spec('websockets'), reason='Chrome/websockets missing')
def test_a_key_typed_while_a_retry_waits_stays_in_its_field(monkeypatch):
    """A provider key typed while a retry waits stays in its field when the reply comes, and the field keeps focus.
    Only a model search hands its text and focus to the new picker, so none of the key reaches the search. The reply
    itself is still held back while the key field has focus and holds text (exo #1100)."""
    s = Planned(monkeypatch, TWO_ROWS)
    retry_gate = threading.Event()
    try:
        with Browser() as b:
            open_at_a_failed_list(b, s, False)
            s.models[:] = [('succeeds', retry_gate)]
            count = s.seen.count(MODELS) + 1
            b.eval(f"{RETRY}.click()")
            arrived(s.seen, MODELS, count)
            b.type(KEY_FIELD, 'synthetic-not-a-key')
            b.eval("window.key = document.activeElement")
            retry_gate.set()
            b.wait("window.replies === 1")
            assert b.eval("[window.key.isConnected, document.activeElement === window.key, window.key.value]") == [
                True, True, 'synthetic-not-a-key']
            assert b.eval(f"{SELECT}.value") == ''
            assert b.eval("window.rejections") == []
    finally:
        retry_gate.set()
        s.srv.close()
