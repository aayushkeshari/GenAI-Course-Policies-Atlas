"""PROV-03/04/05: the contribution timeline page (site/timeline/), tested in a real headless browser.

The page is served from site/ over HTTP and uses no CDN libraries. Without Playwright's Chromium these tests fail
(they do not skip): run `make setup`. Expected values are computed here in Python from site/data/timeline.json,
independently of app.js.
"""
import functools
import http.server
import json
import math
import threading
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright

from provutil import SITE, TIMELINE

pytestmark = [pytest.mark.kind("ui")]

D = json.loads(TIMELINE.read_text(encoding="utf-8"))
ITEMS = D["items"]
BY_ID = {i["id"]: i for i in ITEMS}
PROMPTS = [i for i in ITEMS if i["type"] == "prompt"]
ZOOM_PX = [0, 15, 60, 240, 960]
GAP_CAP_MS = 4 * 3600e3


@pytest.fixture(scope="module")
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(SITE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()  # raises (test error, not skip) if Chromium is missing
        yield b
        b.close()


def open_page(browser, server, params="", width=1280, scheme="light", data=None):
    page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if data is not None:
        page.route("**/data/timeline.json", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(data)))
    page.goto(f"{server}timeline/#{params}")
    page.wait_for_function("window.__tl.ready || window.__tl.errors.length > 0", timeout=20000)
    assert page.evaluate("window.__tl.errors") == [] and not errors, errors
    return page


@pytest.fixture(scope="module")
def page(browser, server):
    p = open_page(browser, server)
    yield p
    p.close()


def go(page, **params):
    page.evaluate("h => { location.hash = h; }", urlencode(params))
    page.wait_for_timeout(60)


def shown_ids(page):
    return page.eval_on_selector_all("#tl-list li.item", "els => els.map(e => e.dataset.id)")


def py_filter(actor="", phase="", type="", cat=""):
    return [i["id"] for i in ITEMS if (not actor or i["actor"] == actor) and (not phase or i["phase"] == phase)
            and (not type or i["type"] == type) and (not cat or (i["type"] == "prompt" and i["category"] == cat))]


# ---------- loading ----------
@pytest.mark.req("PROV-03")
@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("light", 390)])
def test_page_loads_with_banner_and_no_sideways_scroll(browser, server, scheme, width):
    """In light and dark themes and at phone width, the page loads without errors, every view shows the banner
    saying the study's data is synthetic and this page is real redacted history, and nothing scrolls sideways."""
    p = open_page(browser, server, width=width, scheme=scheme)
    for view in ["timeline", "qa", "summary"]:
        go(p, view=view)
        banner = p.locator("#synthetic-banner")
        assert banner.is_visible() and "Synthetic data" in banner.inner_text() and "real" in banner.inner_text()
        assert p.evaluate("document.documentElement.scrollWidth") <= width, view
    p.close()


# ---------- PROV-03 ----------
@pytest.mark.req("PROV-03")
def test_unfiltered_timeline_shows_every_item_in_time_order(page):
    """With no filters the timeline lists every item in timeline.json, oldest first, and says how many."""
    go(page, view="timeline")
    ids = shown_ids(page)
    assert ids == [i["id"] for i in ITEMS]
    assert page.inner_text("#tl-count").startswith(f"{len(ITEMS)} of {len(ITEMS)}")


@pytest.mark.req("PROV-03")
@pytest.mark.parametrize("params", [
    {"actor": "CLAUDE"}, {"actor": "shared"}, {"phase": "P2"}, {"type": "commit"}, {"type": "spec_edit", "actor": "HUMAN"},
    {"cat": "shared"}, {"cat": "human-typed"}, {"actor": "HUMAN", "phase": "P4", "type": "prompt"},
])
def test_filters_show_exactly_the_matching_items(page, params):
    """Each actor / phase / type / prompt-category filter (alone and combined) shows exactly the items a Python
    re-implementation selects, the selects reflect the filter, and the count line agrees."""
    go(page, view="timeline", **params)
    want = py_filter(**params)
    assert shown_ids(page) == want
    assert page.inner_text("#tl-count").startswith(f"{len(want)} of {len(ITEMS)}")
    for key, sel in [("actor", "#f-actor"), ("phase", "#f-phase"), ("type", "#f-type"), ("cat", "#f-cat")]:
        assert page.input_value(sel) == params.get(key, "")


@pytest.mark.req("PROV-03")
def test_filter_controls_update_the_url_and_list(page):
    """Choosing an actor in the select narrows the list and records the filter in the URL hash (shareable)."""
    go(page, view="timeline")
    page.select_option("#f-actor", "HUMAN")
    page.wait_for_timeout(80)
    assert "actor=HUMAN" in page.evaluate("location.hash")
    assert shown_ids(page) == py_filter(actor="HUMAN")


def margins(page):
    return page.eval_on_selector_all("#tl-list li.item", "els => els.map(e => parseInt(e.style.marginTop || '0', 10))")


@pytest.mark.req("PROV-03")
def test_zoom_spaces_items_by_elapsed_time(page):
    """At 'order only' items are packed; at each zoom level the space above an item equals the time since the
    previous item × px-per-hour (gaps capped at 4 h, reset at day headers), so higher zoom spreads the same items
    further apart."""
    totals = []
    for z, pxh in enumerate(ZOOM_PX):
        go(page, view="timeline", zoom=z)
        m = margins(page)
        want, prev = [], None
        for it in ITEMS:
            if prev is None or it["ts"][:10] != prev["ts"][:10]:
                want.append(0)
            else:
                want.append(math.floor(min(it["t"] - prev["t"], GAP_CAP_MS) / 3600e3 * pxh + 0.5))  # JS Math.round
            prev = it
        assert m == want, z
        totals.append(sum(m))
    assert totals[0] == 0 and totals == sorted(totals) and totals[-1] > totals[1]


@pytest.mark.req("PROV-03")
def test_zoom_buttons_and_ctrl_scroll(page):
    """The + and − buttons step through zoom levels (label and URL follow, and are disabled at the ends);
    Ctrl+scroll over the timeline zooms in too."""
    go(page, view="timeline")
    assert page.inner_text("#zoom-label") == "Order only" and page.is_disabled("#zoom-out")
    page.click("#zoom-in")
    page.wait_for_timeout(60)
    assert page.inner_text("#zoom-label") == "15 px per hour" and "zoom=1" in page.evaluate("location.hash")
    page.hover("#tl-list li.item >> nth=0")
    page.keyboard.down("Control")
    page.mouse.wheel(0, -100)
    page.keyboard.up("Control")
    page.wait_for_timeout(80)
    assert page.inner_text("#zoom-label") == "1 px per minute"
    for _ in range(5):
        if not page.is_disabled("#zoom-in"):
            page.click("#zoom-in")
            page.wait_for_timeout(40)
    assert page.is_disabled("#zoom-in") and page.inner_text("#zoom-label") == "16 px per minute"


@pytest.mark.req("PROV-03")
def test_markers_differ_by_shape_and_label_and_have_two_densities(page):
    """Each actor's marker has its own shape class (circle / diamond / outlined square), every row also names its
    actor in text, and the Compact/Clear toggle switches the list between one-line rows and full cards
    (aria-pressed follows)."""
    go(page, view="timeline")
    rows = page.eval_on_selector_all("#tl-list li.item", """els => els.map(e => [e.dataset.actor,
        e.querySelector('.mk').className, e.querySelector('.sr').textContent])""")
    labels = {"HUMAN": "Aayush (human):", "CLAUDE": "Claude:", "shared": "shared / unclear:"}
    for actor, cls, sr in rows:
        assert cls == f"mk {actor}" and sr == labels[actor]
    shapes = page.evaluate("""() => ['HUMAN','CLAUDE','shared'].map(a => {
        const s = getComputedStyle(document.querySelector(`#tl-list .mk.${a}`));
        return [s.borderRadius, s.transform !== 'none', s.borderStyle]; })""")
    assert shapes[0][0] == "50%" and shapes[1][1] and shapes[2][2] == "solid"
    assert len({tuple(s) for s in shapes}) == 3
    assert page.get_attribute("#mode-compact", "aria-pressed") == "true"
    h_compact = page.evaluate("document.querySelector('#tl-list li.item').getBoundingClientRect().height")
    page.click("#mode-clear")
    page.wait_for_timeout(60)
    assert page.get_attribute("#mode-clear", "aria-pressed") == "true" and "clear" in page.get_attribute("#tl-list", "class")
    h_clear = page.evaluate("document.querySelector('#tl-list li.item').getBoundingClientRect().height")
    assert h_clear > h_compact
    page.click("#mode-compact")


@pytest.mark.req("PROV-03")
def test_clicking_an_item_shows_its_details_and_source(page):
    """Clicking a row expands its details (who, type, phase, source; full text for prompts) and toggles
    aria-expanded; clicking again collapses it."""
    go(page, view="timeline", type="prompt")
    first = PROMPTS[0]
    head = page.locator(f'#tl-list li[data-id="{first["id"]}"] button.head')
    head.click()
    det = page.locator(f'#d-{first["id"]}')
    assert det.is_visible() and head.get_attribute("aria-expanded") == "true"
    text = det.inner_text()
    assert first["source"] in text and first["category"] in text and "Aayush (human)" in text
    head.click()
    assert not det.is_visible() and head.get_attribute("aria-expanded") == "false"


# ---------- PROV-04 ----------
def qa_ids(page):
    return page.eval_on_selector_all("#qa-list > li[data-id]", "els => els.map(e => e.dataset.id)")


@pytest.mark.req("PROV-04")
def test_each_prompt_is_shown_with_its_paired_response(page):
    """The Q&A view lists every logged prompt once, in order, each followed by the response timeline.json pairs it
    with (same session), or 'No response logged' when there is none."""
    go(page, view="qa")
    assert qa_ids(page) == [p["id"] for p in PROMPTS]
    for p in PROMPTS:
        li = page.locator(f'#qa-list > li[data-id="{p["id"]}"]')
        a = li.locator(".a").inner_text()
        if p["reply"]:
            assert BY_ID[p["reply"]]["text"][:60].split("\n")[0] in a, p["id"]
            assert BY_ID[p["reply"]]["source"] in a
        else:
            assert "No response logged" in a


@pytest.mark.req("PROV-04")
@pytest.mark.parametrize("q", ["faults", "approve", "PROV-02", "zzz-no-such-text"])
def test_search_matches_prompt_or_response_text(page, q):
    """Searching keeps exactly the pairs whose prompt or response contains the text (case-insensitive), highlights
    the matches, and the count line reports the number."""
    go(page, view="qa", q=q)
    ql = q.lower()
    want = [p["id"] for p in PROMPTS if ql in p["text"].lower()
            or (p["reply"] and ql in BY_ID[p["reply"]]["text"].lower())]
    assert qa_ids(page) == want
    assert page.inner_text("#qa-count").startswith(f"{len(want)} of {len(PROMPTS)}")
    if want:
        marks = page.eval_on_selector_all("#qa-list mark", "els => els.map(e => e.textContent.toLowerCase())")
        assert marks and set(marks) == {ql}


@pytest.mark.req("PROV-04")
def test_typing_in_search_filters_live(page):
    """Typing in the search box filters the list without pressing Enter and stores the query in the URL."""
    go(page, view="qa")
    page.fill("#qa-q", "resume")
    page.wait_for_timeout(300)
    assert "q=resume" in page.evaluate("location.hash")
    assert len(qa_ids(page)) == sum(1 for p in PROMPTS if "resume" in p["text"].lower()
                                    or (p["reply"] and "resume" in BY_ID[p["reply"]]["text"].lower()))


@pytest.mark.req("PROV-04")
def test_timeline_item_links_to_its_exchange(page):
    """A response's details in the timeline link to its exchange in the Q&A view, which opens with that prompt
    focused."""
    resp = next(i for i in ITEMS if i["type"] == "response" and i.get("reply_to"))
    go(page, view="timeline", type="response")
    page.click(f'#tl-list li[data-id="{resp["id"]}"] button.head')
    page.click(f'#d-{resp["id"]} a')
    page.wait_for_timeout(100)
    assert page.evaluate("document.activeElement.dataset.id") == resp["reply_to"]
    assert page.locator(f'#qa-list > li[data-id="{resp["reply_to"]}"]').get_attribute("class") == "focus"


# ---------- PROV-05 ----------
@pytest.mark.req("PROV-05")
def test_summary_table_matches_the_data(page):
    """Every cell of the per-actor table shows timeline.json's count (or — where a measure doesn't apply), and
    rejected plans say that history before the REJECTED: rule is not recorded."""
    go(page, view="summary")
    pa = D["summary"]["per_actor"]
    for metric in pa["HUMAN"]:
        cells = page.eval_on_selector_all(f'#sum-table tr[data-metric="{metric}"] td', "els => els.map(e => e.textContent.trim())")
        for actor, text in zip(D["actors"], cells):
            v = pa[actor][metric]
            if v is None:
                assert text == "—", (metric, actor)
            else:
                assert text.split(" ")[0] == f"{v:,}", (metric, actor, text)
    rej = page.inner_text('#sum-table tr[data-metric="rejected_plans"] td >> nth=0')
    assert "not recorded" in rej and D["summary"]["rules"]["rejected_recorded_since"][:10] in rej
    cats = page.eval_on_selector_all("#cat-table tbody tr", "els => els.map(e => [e.dataset.cat, e.querySelector('td').textContent])")
    assert {c: int(n) for c, n in cats} == D["summary"]["prompt_categories"]
    assert page.inner_text("#kpi-prompts .value") == f"{pa['HUMAN']['prompts']:,}"
    assert page.inner_text("#kpi-approvals .value") == f"{pa['HUMAN']['approvals']:,}"


@pytest.mark.req("PROV-05")
def test_narrative_placeholder_and_rendering(browser, server):
    """With no narrative the summary says it is not yet written; when timeline.json carries one, its paragraphs are
    shown as text (HTML in it is escaped, not run)."""
    if D["narrative"] is None:
        p = open_page(browser, server, "view=summary")
        assert "Narrative not yet written" in p.inner_text("#narrative")
        p.close()
    data = {**D, "narrative": "# Why\n\nI wrote every spec.\n\nClaude wrote the code. <img src=x onerror=alert(1)>"}
    p = open_page(browser, server, "view=summary", data=data)
    body = p.locator("#narrative-body")
    assert body.locator("h3").inner_text() == "Why"
    assert body.locator("p").all_inner_texts() == ["I wrote every spec.", "Claude wrote the code. <img src=x onerror=alert(1)>"]
    assert body.locator("img").count() == 0
    p.close()
