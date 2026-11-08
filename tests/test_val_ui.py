"""VAL-08: the validation explorer's data loading, filters and views, tested in a real headless browser.

The page is served from site/ over HTTP; marked and DOMPurify load from their pinned CDN URLs, so these tests need
the network. Without Playwright's Chromium they fail (they do not skip): run `make setup`.
Expected values are computed here in Python from site/validation/data/, independently of app.js.
"""
import functools
import http.server
import json
import re
import threading
from pathlib import Path
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "validation" / "data"
VIEWS = ["tests", "trace", "coverage", "faults", "claims", "recovery", "review"]

pytestmark = [pytest.mark.kind("ui")]


def j(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


TESTS = j("tests.json")
HISTORY = j("history.json")
TRACE = j("traceability.json")
COVERAGE = j("coverage.json")
FAULTS = j("faults.json")
CLAIMS = j("claims.json")


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


def open_view(browser, server, params="", width=1280, scheme="light"):
    page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}validation/#{params}")
    page.wait_for_function("window.__val.ready || window.__val.errors.length > 0", timeout=20000)
    assert page.evaluate("window.__val.errors") == [] and not errors, errors
    return page


@pytest.fixture(scope="module")
def page(browser, server):
    p = open_view(browser, server, "view=tests")
    yield p
    p.close()


def go(page, **params):
    page.evaluate("h => { location.hash = h; }", urlencode(params))
    page.wait_for_timeout(60)


def py_filter(q="", phase="", kind="", status="", req=""):
    ql = q.lower()
    return [t["nodeid"] for t in TESTS["tests"]
            if (not phase or t["phase"] == phase) and (not kind or t["kind"] == kind) and (not status or t["status"] == status)
            and (not req or req in t["req_ids"])
            and (not ql or ql in t["nodeid"].lower() or ql in t["docstring"].lower() or ql in t["source"].lower())]


# ---------- loading ----------
@pytest.mark.req("VAL-08", "VAL-05")
@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("light", 390)])
def test_every_view_loads_with_banner_and_no_overflow(browser, server, scheme, width):
    """In light and dark mode and at phone width, every view loads its data with no JS errors, shows its panel and
    the synthetic-data banner, and has no horizontal page scroll."""
    page = open_view(browser, server, "view=tests", width=width, scheme=scheme)
    for v in VIEWS:
        go(page, view=v)
        assert page.locator(f"#view-{v}").is_visible(), v
        assert page.locator("#synthetic-banner").is_visible() and "Synthetic data" in page.inner_text("#synthetic-banner")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (v, width)
        assert page.evaluate("window.__val.errors") == []
    page.close()


@pytest.mark.req("VAL-08")
def test_missing_data_file_shows_an_error_not_a_blank_page(browser, server):
    """If a data file fails to load (here tests.json returns 404), the page says what failed and how to serve the
    site, instead of rendering empty tables."""
    page = browser.new_page()
    page.route("**/validation/data/tests.json", lambda r: r.fulfill(status=404, body="nope"))
    page.goto(f"{server}validation/")
    page.wait_for_function("window.__val.errors.length > 0", timeout=20000)
    msg = page.inner_text("#load-error")
    assert page.locator("#load-error").is_visible() and "tests.json" in msg and "make serve" in msg
    page.close()


@pytest.mark.req("VAL-08", "VAL-02")
def test_header_numbers_match_the_data(page):
    """The snapshot line and the Tests KPIs show the run file, test count, run count and requirements-with-tests
    count from the data files."""
    go(page, view="tests")
    assert TESTS["run"] in page.inner_text("#run-line")
    assert page.inner_text('#k-tests [data-k="n"]') == str(TESTS["n"])
    assert page.inner_text('#k-runs [data-k="runs"]') == str(len(HISTORY["runs"]))
    assert page.inner_text('#k-reqs [data-k="reqs"]') == str(sum(1 for r in TRACE["requirements"] if r["tests"]))


# ---------- filters ----------
FILTER_CASES = [
    {}, {"phase": "P4"}, {"kind": "fault"}, {"kind": "ui"}, {"status": "passed"}, {"req": "VAL-04"},
    {"q": "redact"}, {"q": "ground truth"}, {"phase": "P2", "kind": "unit", "q": "bootstrap"}, {"req": "DASH-01", "kind": "ui"},
]


@pytest.mark.req("VAL-08", "VAL-05")
@pytest.mark.parametrize("f", FILTER_CASES, ids=lambda f: "-".join(f"{k}={v}" for k, v in f.items()) or "none")
def test_filters_show_exactly_the_matching_tests(page, f):
    """For each filter combination set through the URL hash, the visible rows are exactly the tests a Python filter
    over tests.json selects (same set, same count), and the selects reflect the hash."""
    go(page, view="tests", **f)
    expected = py_filter(**f)
    rows = page.eval_on_selector_all("#test-table tbody tr", "rs => rs.map(r => r.dataset.nodeid)")
    assert sorted(rows) == sorted(expected)
    assert page.inner_text("#test-count") == f"Showing {len(expected)} of {TESTS['n']} tests"
    for k in ("phase", "kind", "status", "req"):
        assert page.input_value(f"#f-{k}") == f.get(k, "")


@pytest.mark.req("VAL-08", "VAL-05")
def test_filter_controls_update_the_list_and_the_url(page):
    """Choosing a filter in the form (not the URL) narrows the list and writes the filter into the hash, so the view can
    be shared; Clear resets everything."""
    go(page, view="tests")
    page.select_option("#f-kind", "property")
    page.wait_for_timeout(80)
    assert "kind=property" in page.evaluate("location.hash")
    assert page.locator("#test-table tbody tr").count() == len(py_filter(kind="property"))
    page.fill("#f-q", "seed")
    page.wait_for_timeout(300)
    assert page.locator("#test-table tbody tr").count() == len(py_filter(kind="property", q="seed"))
    page.click("#f-clear")
    page.wait_for_timeout(80)
    assert page.locator("#test-table tbody tr").count() == TESTS["n"]


# ---------- detail ----------
@pytest.mark.req("VAL-08", "VAL-05", "VAL-02")
def test_clicking_a_test_shows_docstring_source_history_and_spec_text(page):
    """Clicking a row selects it and shows that test's docstring, source, a history strip with one cell per run, the
    pass count over the runs it was part of, and the spec text of each requirement it covers."""
    t = next(x for x in TESTS["tests"] if x["nodeid"].endswith("test_bodies_are_content_addressed_and_written_once"))
    go(page, view="tests", req="VAL-01")
    page.click(f'#test-table tbody tr[data-nodeid="{t["nodeid"]}"] td.nodeid')
    page.wait_for_timeout(80)
    assert page.locator(f'#test-table tbody tr[data-nodeid="{t["nodeid"]}"]').get_attribute("aria-selected") == "true"
    assert page.inner_text("#detail-title") == t["nodeid"]
    doc = " ".join(t["docstring"].split())
    assert " ".join(page.inner_text("#detail-doc").split()) == doc
    assert page.inner_text("#detail-src").rstrip("\n") == t["source"].rstrip("\n")
    letters = HISTORY["tests"][t["nodeid"]]
    assert page.locator("#test-detail .strip.big i").count() == len(letters) == len(HISTORY["runs"])
    ran = sum(1 for c in letters if c != ".")
    assert f"Passed in {letters.count('p')} of the {ran} runs" in page.inner_text("#detail-hist")
    reqs = {r["id"]: r for r in TRACE["requirements"]}
    detail = page.inner_text("#test-detail")
    for rid in t["req_ids"]:
        assert " ".join(reqs[rid]["text"].split())[:80] in " ".join(detail.split())


@pytest.mark.req("VAL-08", "VAL-05")
def test_deep_link_to_a_test_and_keyboard_selection(browser, server):
    """A URL naming a test opens it directly; in the list, Enter on a focused row selects that row."""
    t = TESTS["tests"][3]
    page = open_view(browser, server, urlencode({"view": "tests", "test": t["nodeid"]}))
    assert page.inner_text("#detail-title") == t["nodeid"]
    row = page.locator("#test-table tbody tr").nth(7)
    row.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(80)
    assert page.inner_text("#detail-title") == TESTS["tests"][7]["nodeid"]
    page.close()


# ---------- traceability ----------
@pytest.mark.req("VAL-08", "VAL-03")
def test_traceability_rows_statuses_and_red_untested(page):
    """The matrix shows all requirements with their status; the KPI counts match; requirements with no tests are
    rendered red with a 'no tests' label; filters by phase and status give the expected rows."""
    go(page, view="trace")
    rows = page.eval_on_selector_all("#trace-table tbody tr", "rs => rs.map(r => [r.dataset.req, r.dataset.status])")
    assert rows == [[r["id"], r["status"]] for r in TRACE["requirements"]]
    for s in ("passing", "partial", "failing", "untested"):
        assert page.inner_text(f'#k-{s} [data-k="{s}"]') == str(TRACE["counts"].get(s, 0))
    untested = [r["id"] for r in TRACE["requirements"] if r["status"] == "untested"]
    for rid in untested:
        cell = page.locator(f"#req-{rid} td.rid")
        assert page.locator(f"#req-{rid} .pill").inner_text().strip().endswith("no tests")
        color = cell.evaluate("e => getComputedStyle(e).color")
        assert color == "rgb(180, 35, 35)", (rid, color)  # --critical-ink, light theme
    go(page, view="trace", phase="P4", status="passing")
    shown = page.eval_on_selector_all("#trace-table tbody tr", "rs => rs.map(r => r.dataset.req)")
    assert shown == [r["id"] for r in TRACE["requirements"] if r["phase"] == "P4" and r["status"] == "passing"]


@pytest.mark.req("VAL-08", "VAL-03")
def test_requirement_test_count_links_to_its_tests(page):
    """A requirement's test count links to the Tests view filtered to that requirement, showing exactly its tests."""
    r = next(x for x in TRACE["requirements"] if x["id"] == "VAL-04")
    go(page, view="trace")
    page.click("#req-VAL-04 td.n a")
    page.wait_for_timeout(80)
    assert page.locator("#view-tests").is_visible()
    rows = page.eval_on_selector_all("#test-table tbody tr", "rs => rs.map(r => r.dataset.nodeid)")
    assert sorted(rows) == sorted(r["tests"]) and len(rows) == len(r["tests"])


# ---------- coverage, faults, claims, recovery, review ----------
@pytest.mark.req("VAL-08", "VAL-03")
def test_coverage_table_matches_the_data(page):
    """The total and one row per module show the pytest-cov figures for the snapshot run."""
    go(page, view="coverage")
    assert page.inner_text('#k-cov [data-k="total"]') == f"{COVERAGE['totals']['percent']:.1f}%"
    rows = page.eval_on_selector_all("#cov-table tbody tr", "rs => rs.map(r => [r.dataset.module, r.cells[3].innerText])")
    assert rows == [[m["module"], f"{m['percent']:.1f}%"] for m in COVERAGE["modules"]]


@pytest.mark.req("VAL-08", "VAL-04")
def test_fault_page_shows_rates_every_fault_and_lists_uncaught(page):
    """The fault view shows the detection rate and the behavioural rate from faults.json, one card per fault with
    its caught/not-caught label, an explicit uncaught list ('None.' only when there are none), the golden-only
    faults, and the UI-test policy text."""
    go(page, view="faults")
    assert page.inner_text('#k-rate [data-k="rate"]') == f"{round(FAULTS['detection_rate'] * 100)}%"
    assert page.inner_text('#k-brate [data-k="brate"]') == f"{round(FAULTS['behavioral_detection_rate'] * 100)}%"
    assert page.inner_text('#k-uncaught [data-k="uncaught"]') == str(len(FAULTS["uncaught"]))
    cards = page.eval_on_selector_all(".fault", "fs => fs.map(f => [f.dataset.fault, f.querySelector('.pill').innerText.trim()])")
    assert [c[0] for c in cards] == [f["id"] for f in FAULTS["faults"]]
    for (fid, label), f in zip(cards, FAULTS["faults"]):
        assert label.endswith("caught") and ("not caught" in label) == (not f["caught"]), fid
    unc = page.inner_text("#fault-uncaught")
    assert unc.startswith("None.") if not FAULTS["uncaught"] else all(i in unc for i in FAULTS["uncaught"])
    for fid in FAULTS["golden_only"]:
        assert fid in page.inner_text("#fault-golden")
    assert "excluded from fault runs" in page.inner_text("#fault-method") and "F09" not in FAULTS["uncaught"]


@pytest.mark.req("VAL-08", "VAL-06")
def test_dashboard_evidence_link_opens_the_claim(browser, server):
    """On the dashboard, a panel's Evidence link opens the explorer's Claims view at that claim, which lists exactly the
    claim's supporting tests with their statuses."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"{server}dashboard/#view=policy")
    page.wait_for_function("window.__dash && window.__dash.ready", timeout=20000)
    page.click("#panel-se a.evidence")
    page.wait_for_function("window.__val && window.__val.ready", timeout=20000)
    assert page.locator("#view-claims").is_visible()
    claim = next(c for c in CLAIMS["claims"] if c["id"] == "se")
    el = page.locator("#claim-se")
    assert "focus" in el.get_attribute("class")
    assert el.locator("li").count() == len(claim["tests"])
    assert page.locator(".claim").count() == len(CLAIMS["claims"])
    page.close()


@pytest.mark.req("VAL-08", "VAL-05")
def test_recovery_view_is_separate_and_labelled_validation_only(page):
    """The truth-derived results appear only on a tab labelled exactly 'Recovery vs. ground truth (validation only)',
    with a note saying they are not on the findings dashboard; the planted-direction rows match recovery.json."""
    assert page.inner_text("#tab-recovery").strip() == "Recovery vs. ground truth (validation only)"
    go(page, view="recovery")
    note = page.inner_text("#recovery-note")
    assert "Validation only" in note and "none of this appears on the findings dashboard" in note
    rec = json.loads((DATA / "recovery" / "recovery.json").read_text())
    ids = page.eval_on_selector_all("#rec-planted tbody tr[data-claim]", "rs => rs.map(r => r.dataset.claim)")
    assert ids == list(rec["directions"]) + list(rec["null"])


@pytest.mark.req("VAL-08", "VAL-07")
def test_review_log_renders_every_entry(page):
    """docs/review-log.md renders as HTML (sanitised): every '## ' heading becomes a heading on the page, next to the
    automated-evidence summary for the same snapshot."""
    go(page, view="review")
    md = (DATA / "review-log.md").read_text()
    headings = [h.strip() for h in re.findall(r"^## (.+)$", md, flags=re.M)]
    shown = page.eval_on_selector_all("#review-body h2", "hs => hs.map(h => h.innerText.trim())")
    assert shown == headings and len(headings) >= 3
    assert f"of {TESTS['n']} tests passed" in page.inner_text("#review-side")
    assert page.locator("#review-body script").count() == 0


@pytest.mark.req("VAL-08")
def test_keyboard_tabs_and_aria(browser, server):
    """Tabs have tab/tabpanel roles; arrow keys move between views and update the URL; only the selected tab is in
    the tab order."""
    page = open_view(browser, server, "view=tests")
    page.focus("#tab-tests")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(80)
    assert "view=trace" in page.evaluate("location.hash") and page.locator("#view-trace").is_visible()
    assert page.get_attribute("#tab-trace", "aria-selected") == "true" and page.get_attribute("#tab-tests", "tabindex") == "-1"
    page.keyboard.press("End")
    page.wait_for_timeout(80)
    assert page.locator("#view-review").is_visible()
    for v in VIEWS:
        assert page.get_attribute(f"#view-{v}", "role") == "tabpanel"
        assert page.get_attribute(f"#view-{v}", "aria-labelledby") == f"tab-{v}"
    page.close()


@pytest.mark.req("VAL-08")
def test_cdn_libraries_pinned_and_no_build_step():
    """Every external script is an exact-version URL on an allowed CDN, the page has no module imports or bundler
    output, and the explorer's stylesheet defines its status colours for both themes."""
    html = (SITE / "validation" / "index.html").read_text()
    srcs = re.findall(r'<script src="([^"]+)"', html)
    external = [s for s in srcs if s.startswith("http")]
    assert external == ["https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js",
                        "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js"]
    assert [s for s in srcs if not s.startswith("http")] == ["app.js"]
    js = (SITE / "validation" / "app.js").read_text()
    assert not re.search(r"^\s*(import|export)\s", js, re.M) and "require(" not in js
    css = (SITE / "validation" / "style.css").read_text()
    assert css.count("--critical-ink") >= 3 and ':root[data-theme="dark"]' in css
