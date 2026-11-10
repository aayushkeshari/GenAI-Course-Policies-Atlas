"""TOK-06/07: the usage-limit log and the token page (site/tokens/), the page tested in a real headless browser.

Expected values are computed here in Python from results/tokens.json and site/tokens/data/tokens.json,
independently of app.js. The page uses no CDN libraries.
"""
import functools
import http.server
import json
import threading

import pytest
from playwright.sync_api import sync_playwright

from src.tokens import build_tokens as K
from tokutil import RESULT, ROOT

SITE = ROOT / "site"
BUNDLE = SITE / "tokens" / "data" / "tokens.json"
D = json.loads(BUNDLE.read_text(encoding="utf-8"))


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
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, server, width=1280, scheme="light", data=None):
    page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if data is not None:
        page.route("**/tokens/data/tokens.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(data)))
    page.goto(f"{server}tokens/")
    page.wait_for_function("window.__tok.ready || window.__tok.errors.length > 0", timeout=20000)
    assert page.evaluate("window.__tok.errors") == [] and not errors, errors
    return page


@pytest.fixture(scope="module")
def page(browser, server):
    p = open_page(browser, server)
    yield p
    p.close()


# ---------- TOK-06 ----------
@pytest.mark.req("TOK-06")
def test_usage_limit_table_is_parsed(tmp_path):
    """The hand-kept markdown table is read row by row: the header and separator are skipped, blank rows are
    ignored, missing trailing cells become empty, and each row maps to when/plan/what/phase/notes."""
    f = tmp_path / "usage-limits.md"
    f.write_text("# Usage\n\ntext | not a table\n\n| When | Plan | What happened | Phase | Notes |\n|---|---|---|---|---|\n"
                 "| 2026-11-09T10:00:00-05:00 | Pro | 5-hour limit hit | P3 | waited 40 min |\n| | | | | |\n"
                 "| 2026-11-09T18:00:00-05:00 | Pro | warning at 80% | P4 |\n")
    assert K.read_usage_limits(f) == [
        {"when": "2026-11-09T10:00:00-05:00", "plan": "Pro", "what": "5-hour limit hit", "phase": "P3", "notes": "waited 40 min"},
        {"when": "2026-11-09T18:00:00-05:00", "plan": "Pro", "what": "warning at 80%", "phase": "P4", "notes": ""}]
    assert K.read_usage_limits(tmp_path / "missing.md") == []


@pytest.mark.req("TOK-06")
def test_committed_usage_log_reaches_the_page_data():
    """docs/usage-limits.md exists with the expected columns, and the page data carries exactly its rows."""
    text = (ROOT / "docs" / "usage-limits.md").read_text(encoding="utf-8")
    assert "| When | Plan | What happened | Phase | Notes |" in text
    assert D["usage_limits"] == K.read_usage_limits(ROOT / "docs" / "usage-limits.md")


@pytest.mark.req("TOK-06", "TOK-07")
def test_usage_limits_show_on_the_page(browser, server, page):
    """With no logged events the page says so; with events in the data each one is a table row (text escaped)."""
    if not D["usage_limits"]:
        assert page.inner_text("#limits-empty") == "No usage-limit events logged yet."
    data = {**D, "usage_limits": [{"when": "2026-11-09T10:00", "plan": "Pro", "what": "limit <b>hit</b>", "phase": "P3", "notes": ""}]}
    p = open_page(browser, server, data=data)
    cells = p.eval_on_selector_all("#limits tbody td", "els => els.map(e => e.textContent)")
    assert cells[:3] == ["2026-11-09T10:00", "Pro", "limit <b>hit</b>"]
    p.close()


# ---------- TOK-07 ----------
@pytest.mark.req("TOK-07")
def test_page_data_matches_the_results():
    """site/tokens/data/tokens.json is exactly site_bundle(results/tokens.json): same metrics, experiment and
    boundaries, slim rows (no message ids, short session ids), not marked synthetic."""
    res = json.loads(RESULT.read_text(encoding="utf-8"))
    assert D == json.loads(json.dumps(K.site_bundle(res)))
    assert D["synthetic"] is False and "message_id" not in D["rows"][0] and len(D["rows"][0]["session_id"]) == 8


@pytest.mark.req("TOK-07")
@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("light", 390)])
def test_page_loads_with_banner_and_no_sideways_scroll(browser, server, scheme, width):
    """In light and dark themes and at phone width the page loads without errors, the banner says the study data is
    synthetic while this page shows real usage, and nothing scrolls sideways."""
    p = open_page(browser, server, width=width, scheme=scheme)
    banner = p.inner_text("#synthetic-banner")
    assert "Synthetic data" in banner and "real" in banner
    assert p.evaluate("document.documentElement.scrollWidth") <= width
    p.close()


@pytest.mark.req("TOK-07")
def test_kpis_and_group_bars_match_the_data(page):
    """The headline tiles show the total, the cache-read share and the output count, and the phase and activity
    charts have one bar per group whose value is that group's total."""
    t = D["metrics"]["totals"]
    assert f"{t['total']:,}" in page.inner_text("#kpi-total")
    assert page.inner_text("#kpi-cache .value") == f"{t['cache_read_share'] * 100:.1f}%"
    for chart, metric in [("#c-phase", "by_phase"), ("#c-activity", "by_activity")]:
        bars = page.eval_on_selector_all(f"{chart} path.bar", "els => els.map(e => [e.dataset.key, +e.dataset.value])")
        assert bars == [[k, v["total"]] for k, v in D["metrics"][metric].items()], chart


@pytest.mark.req("TOK-07", "TOK-03", "TOK-04")
def test_context_chart_draws_every_message_and_marks_boundaries(page):
    """The context line has one point per main-session message (subagents excluded), and there is one dashed line
    per /clear and one dotted line per /compact, labelled, matching the boundaries in the data."""
    d = page.get_attribute("#c-context path.ctx", "d")
    assert d.count("L") + d.count("M") == sum(1 for r in D["rows"] if not r["sidechain"])
    kinds = page.eval_on_selector_all("#c-context line.bound", "els => els.map(e => e.dataset.kind)")
    assert kinds == [b["kind"] for b in D["boundaries"]]
    labels = page.eval_on_selector_all("#c-context text.blabel", "els => els.map(e => e.textContent)")
    assert labels == ["/clear" if b["kind"] == "clear" else "/compact" for b in D["boundaries"]]


@pytest.mark.req("TOK-07", "TOK-04")
def test_prompt_chart_has_one_bar_per_prompt(page):
    """Tokens per prompt: one bar per logged prompt in order, each with that prompt's total."""
    vals = page.eval_on_selector_all("#c-prompt path.bar", "els => els.map(e => +e.dataset.value)")
    assert vals == [p["total"] for p in D["metrics"]["per_prompt"]]


@pytest.mark.req("TOK-07", "TOK-05")
def test_experiment_table_states_status_and_small_sample(page):
    """The experiment table has rows A, B and C with each condition's status from the data, the n = 1 caveat is
    shown, and runs excluded for not following the protocol are listed with their reasons."""
    rows = page.eval_on_selector_all("#exp-table tbody tr", "els => els.map(e => [e.dataset.cond, e.dataset.status])")
    assert rows == [[c, v["status"]] for c, v in D["experiment"]["conditions"].items()]
    cav = page.inner_text("#exp-caveat")
    assert "Small sample" in cav and "n = 1" in cav and "anecdotal" in cav
    for x in D["experiment"]["excluded"]:
        assert f"line {x['event_line']}" in page.inner_text("#exp-excluded") and x["reason"] in page.inner_text("#exp-excluded")


@pytest.mark.req("TOK-07")
def test_table_toggles_show_and_hide(page):
    """Each 'Show table' button reveals its table and flips aria-expanded; pressing again hides it."""
    for btn in page.query_selector_all(".tbl-toggle"):
        target = page.locator("#" + btn.get_attribute("aria-controls"))
        btn.click()
        assert btn.get_attribute("aria-expanded") == "true" and target.is_visible() and target.locator("tbody tr").count() > 0
        btn.click()
        assert btn.get_attribute("aria-expanded") == "false" and not target.is_visible()


@pytest.mark.req("TOK-07")
def test_what_i_learned_placeholder_and_rendering(browser, server, page):
    """Without docs/tokens-learned.md the section says it is not written yet; with text, paragraphs render as plain
    text (HTML escaped, not run)."""
    if D["learned"] is None:
        assert "Not written yet" in page.inner_text("#learned")
    p = open_page(browser, server, data={**D, "learned": "Clearing helps.\n\n<img src=x onerror=alert(1)>"})
    assert p.locator("#learned p").all_inner_texts() == ["Clearing helps.", "<img src=x onerror=alert(1)>"]
    assert p.locator("#learned img").count() == 0
    p.close()


@pytest.mark.req("TOK-07")
def test_what_i_learned_bold_title_and_bullets(browser, server):
    """A lone **bold** line renders as a heading and a block of '- ' lines renders as a list, escaped, so Aayush's
    markdown in docs/tokens-learned.md shows no raw asterisks or dashes."""
    text = "**Title**\n\n- One <b>x</b>.\n- Two."
    p = open_page(browser, server, data={**D, "learned": text})
    assert p.locator("#learned h3").all_inner_texts() == ["Title"]
    assert p.locator("#learned li").all_inner_texts() == ["One <b>x</b>.", "Two."]
    assert p.locator("#learned b").count() == 0
    p.close()
