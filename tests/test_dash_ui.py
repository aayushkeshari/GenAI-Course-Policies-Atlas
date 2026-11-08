"""DASH-02..08 dashboard tests in a real headless browser (Playwright, Chromium).

The page is served from site/ over HTTP. Chart.js loads from its pinned CDN URL, so these tests need the network.
Without Playwright's Chromium they fail (they do not skip): run `make setup`.
"""
import functools
import http.server
import json
import math
import re
import threading
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "data"
RESULTS = ROOT / "results"
VIEWS = ["summary", "policy", "uses", "statements", "model", "coder", "explorer", "drilldown"]
CHART_VIEWS = ["policy", "uses", "statements", "model", "coder"]
ROW_FILES = {"institutions.json", "courses.json", "statements.json"}

pytestmark = [pytest.mark.kind("ui")]


# ---------- independent formatter and pointer resolver (mirror of app.js FMT, written separately) ----------
def _q(v: float, places: str) -> str:
    """JS Number.prototype.toFixed: exact value of the double, ties away from zero."""
    return str(Decimal(v).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def fmt(v, kind: str) -> str:
    return {
        "int": lambda: str(int(math.floor(v + 0.5))),
        "f2": lambda: _q(v, "0.01"),
        "f3": lambda: _q(v, "0.001"),
        "pct0": lambda: _q(v * 100, "1") + "%",
        "pct1": lambda: _q(v * 100, "0.1") + "%",
        "pp0": lambda: _q(v * 100, "1"),
        "p3": lambda: "<0.001" if v < 0.001 else _q(v, "0.001"),
    }[kind]()


@functools.lru_cache(maxsize=None)
def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(src: str):
    """Resolve 'file.json#/a/0/b'. Results files resolve against results/ (the source of truth); row files
    against site/data/ (they exist only there)."""
    file, ptr = src.split("#")
    o = load((DATA if file in ROW_FILES else RESULTS) / file)
    for part in ptr.split("/")[1:]:
        o = o[int(part)] if isinstance(o, list) else o[part]
    return o


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(SITE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/dashboard/"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()  # raises (test error, not skip) if Chromium is missing
        yield b
        b.close()


class Page:
    def __init__(self, browser, url, scheme="light", width=1280):
        self.page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
        self.errors = []
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(url)
        self.page.wait_for_function("window.__dash && (window.__dash.ready || window.__dash.errors.length > 0)")
        self.errors += self.page.evaluate("window.__dash.errors")

    def view(self, v, extra=""):
        self.page.evaluate(f"location.hash = 'view={v}{extra}'")
        self.page.wait_for_function(f"!document.getElementById('view-{v}').hidden")
        self.page.wait_for_timeout(50)

    def ev(self, js, arg=None):
        return self.page.evaluate(js, arg)


@pytest.fixture(scope="module")
def page(browser, server):
    """One light, desktop page with every view built and every data table opened."""
    p = Page(browser, server)
    for v in VIEWS:
        p.view(v)
    for v in CHART_VIEWS:
        p.view(v)
        p.ev(f"document.querySelectorAll('#view-{v} .table-toggle').forEach(b => b.click())")
    yield p
    p.page.close()


# ---------- DASH-07: loads cleanly, charts populated ----------
@pytest.mark.req("DASH-07")
@pytest.mark.req("DASH-06")
@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("light", 375), ("dark", 375)])
def test_every_view_loads_without_errors_and_every_chart_is_drawn(browser, server, scheme, width):
    """Each view loads in light and dark mode at 1280px and 375px with no console or page errors. Every canvas
    on a chart view has a registered Chart.js chart with at least one data point and visible pixels, and the
    page never scrolls sideways (DASH-06)."""
    p = Page(browser, server, scheme, width)
    canvases = 0
    for v in VIEWS:
        p.view(v)
        assert p.ev("document.documentElement.scrollWidth") <= width, f"{v}: horizontal scroll at {width}px"
        info = p.ev(f"""[...document.querySelectorAll('#view-{v} canvas')].map(c => {{
            const ch = window.__dash.charts[c.id];
            const px = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let ink = 0; for (let i = 3; i < px.length; i += 4) if (px[i] > 0) ink++;
            return {{ id: c.id, chart: !!ch, points: ch ? ch.data.datasets.reduce((n, d) => n + d.data.length, 0) : 0,
                     ink, w: c.width, h: c.height }};
        }})""")
        if v in CHART_VIEWS:
            assert info, f"{v}: no canvas"
        for c in info:
            assert c["chart"] and c["points"] > 0, c
            assert c["w"] > 0 and c["h"] > 0 and c["ink"] > 0.01 * c["w"] * c["h"], f"{v}/{c['id']} looks blank: {c}"
        canvases += len(info)
    assert canvases == 13
    assert p.errors == []
    p.page.close()


# ---------- DASH-07: every number matches its source ----------
@pytest.mark.req("DASH-07")
def test_every_displayed_number_matches_results_json(page):
    """Every number in text, KPI tiles and data tables is a [data-src] span; its text equals the value at that JSON
    pointer in results/<file>.json (row files: site/data/), formatted by an independent re-implementation of the
    page's formatter. Covers every view, with every data table open."""
    spans = page.ev("[...document.querySelectorAll('[data-src]')].map(e => [e.dataset.src, e.dataset.fmt, e.textContent])")
    assert len(spans) > 400
    bad = [(src, f, text, fmt(resolve(src), f)) for src, f, text in spans if text != fmt(resolve(src), f)]
    assert bad == []
    files = {s.split("#")[0] for s, _, _ in spans}
    assert {"descriptives.json", "allowed_uses.json", "assessment.json", "association.json", "regression.json",
            "rhetoric.json", "coder_eval.json", "kappa.json", "statements.json", "courses.json", "institutions.json"} <= files


@pytest.mark.req("DASH-07")
def test_every_chart_value_matches_its_source(page):
    """Every value plotted in every chart has a JSON pointer (dataset.srcs, same shape as the data) and equals the
    value at that pointer in results/*.json. No chart plots an unsourced number."""
    charts = page.ev("""Object.entries(window.__dash.charts).map(([id, ch]) => [id, ch.data.datasets.map(d =>
        ({ label: d.label, data: d.data.map(x => (x && typeof x === 'object' && !Array.isArray(x)) ?
            Object.fromEntries(Object.entries(x).filter(([k, v]) => typeof v === 'number')) : x), srcs: d.srcs }))])""")
    assert len(charts) == 13
    checked = 0
    for cid, datasets in charts:
        for ds in datasets:
            assert ds["srcs"] is not None and len(ds["srcs"]) == len(ds["data"]), f"{cid}/{ds['label']}: missing srcs"
            for value, src in zip(ds["data"], ds["srcs"]):
                if isinstance(value, list):
                    pairs = list(zip(value, src))
                elif isinstance(value, dict):
                    assert set(value) == set(src), (cid, value, src)
                    pairs = [(value[k], src[k]) for k in value]
                else:
                    pairs = [(value, src)]
                for v, s in pairs:
                    assert v == pytest.approx(resolve(s), abs=1e-12), (cid, ds["label"], s)
                    checked += 1
    # scatter 135 x 2 + level 20 + SE 10 + term 21 + region 8 + heatmap 20 + assessment 25 + stance 5 + themes 3
    # + coefficients 9 + 2 x 18 CI ends + F1 16 + kappa 8
    assert checked == 451


@pytest.mark.req("DASH-07")
def test_tables_and_tiles_show_no_unsourced_numbers(page):
    """Inside data tables, KPI tiles, takeaways and panel notes, removing the [data-src] spans leaves no digits
    except fixed labels (policy/stance scale names, CI level, term and year names, the commit id). So no number
    is hand-typed into the page."""
    leftovers = page.ev("""[...document.querySelectorAll('td.n, .kpi .value, .kpi .sub, .takeaway, .panel-note')].map(e => {
        const c = e.cloneNode(true); c.querySelectorAll('[data-src], code').forEach(s => s.remove()); return c.textContent; })""")
    allowed = re.compile(r"95%|[FS]2[3-6]|20\d\d|\b[0-4] (?:prohibited|=)|\(0–4\)|−2 to \+2|0 = |≥ 1|policy [0-4]|policy 0|\bF1s?\b|"
                         r"[−+]?[0-2] (?:Prohibitive|Cautious|Neutral|Supportive|Enthusiastic)")
    bad = [t for t in leftovers if re.search(r"\d", allowed.sub("", t))]
    assert bad == []


# ---------- DASH-02 ----------
@pytest.mark.req("DASH-02")
def test_synthetic_banner_visible_on_every_view(browser, server):
    """On every view, at desktop and phone widths, the 'Synthetic data — illustrative only' banner is in the
    viewport when the view opens, and the loaded data files are all flagged synthetic."""
    for width in (1280, 375):
        p = Page(browser, server, width=width)
        for v in VIEWS:
            p.view(v)
            p.ev("window.scrollTo(0, 0)")
            box = p.page.locator("#synthetic-banner").bounding_box()
            assert box and box["height"] > 0 and box["y"] < 900, (v, width)
            assert "Synthetic data — illustrative only" in p.page.locator("#synthetic-banner").inner_text()
        p.page.close()
    for f in DATA.glob("*.json"):
        assert load(f)["synthetic"] is True


# ---------- DASH-05 ----------
@pytest.mark.req("DASH-05")
def test_each_chart_has_takeaway_table_toggle_and_source_link(browser, server):
    """Every chart panel has exactly one one-sentence takeaway, a data-table toggle that shows and hides a table
    (aria-expanded follows), and source links that point at JSON files that exist in site/data/."""
    p = Page(browser, server)
    panels = 0
    for v in CHART_VIEWS:
        p.view(v)
        for el in p.page.locator(f"#view-{v} .panel").all():
            panels += 1
            take = el.locator(".takeaway")
            assert take.count() == 1
            text = take.inner_text().strip()
            sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if s]
            # the scatter adds one instruction sentence ("Select a dot ...")
            assert len([s for s in sentences if not s.startswith("Select a dot")]) == 1, text
            btn, wrap = el.locator(".table-toggle"), el.locator(".table-wrap")
            assert wrap.is_hidden() and btn.get_attribute("aria-expanded") == "false"
            btn.click()
            assert wrap.is_visible() and btn.get_attribute("aria-expanded") == "true"
            assert wrap.locator("table tbody tr").count() > 0
            btn.click()
            assert wrap.is_hidden()
            links = [a.get_attribute("href") for a in el.locator(".panel-foot a").all()]
            assert links and all((DATA / Path(h).name).exists() and h.startswith("../data/") for h in links)
    assert panels == 11
    p.page.close()


# ---------- DASH-04 ----------
@pytest.mark.req("DASH-04")
def test_statement_explorer_search_and_filters(browser, server):
    """Text search and the stance, theme, type and year filters return exactly the statements a direct filter of
    statements.json returns, and each card shows the coded labels and rule IDs next to the text."""
    S = load(DATA / "statements.json")["statements"]
    p = Page(browser, server)
    p.view("explorer")

    def matches():
        return int(p.page.locator('[data-derived="matches"]').inner_text())

    assert matches() == len(S)
    p.page.fill("#f-q", "honor code")
    assert matches() == sum("honor code" in s["text"].lower() for s in S) > 0
    assert p.page.locator("#explorer-list mark").count() > 0
    p.page.click("#f-reset")
    p.page.select_option("#f-stance", "-2")
    p.page.select_option("#f-theme", "mentions_integrity")
    assert matches() == sum(s["coded_stance"] == -2 and s["coded_mentions_integrity"] for s in S)
    p.page.select_option("#f-theme", "none")
    p.page.select_option("#f-stance", "")
    assert matches() == sum(not any(s[f"coded_{t}"] for t in ["mentions_integrity", "mentions_collaboration", "mentions_careers"]) for s in S)
    p.page.click("#f-reset")
    p.page.select_option("#f-type", "faq")
    p.page.select_option("#f-year", "2025")
    expect = [s for s in S if s["pub_type"] == "faq" and s["year"] == "2025"]
    assert matches() == len(expect)
    first = p.page.locator("#explorer-list .stmt").first
    s0 = expect[0]
    assert first.get_attribute("data-stmt") == s0["stmt_id"]
    assert s0["text"] in first.locator(".text").inner_text()
    assert s0["coded_stance_rule"] in first.inner_text()
    assert p.errors == []
    p.page.close()


# ---------- DASH-08 ----------
@pytest.mark.req("DASH-08")
def test_clicking_a_scatter_dot_opens_that_institution(browser, server):
    """Clicking a highlighted (top-decile) dot in the rhetoric-vs-practice scatter opens the drilldown for that
    institution, which shows its course-term policies from courses.json and its statements, and a note that the
    gap can reflect coder errors (e.g. the unhandled "far from banning" negation)."""
    p = Page(browser, server)
    p.view("statements")
    target = p.ev("""(() => { const ch = window.__dash.charts['c-scatter'], el = ch.getDatasetMeta(1).data[0];
        const r = ch.canvas.getBoundingClientRect(); return { x: r.left + el.x, y: r.top + el.y, id: ch.data.datasets[1].data[0].inst_id }; })()""")
    p.page.locator("#c-scatter").scroll_into_view_if_needed()
    target.update(p.ev("""(() => { const ch = window.__dash.charts['c-scatter'], el = ch.getDatasetMeta(1).data[0];
        const r = ch.canvas.getBoundingClientRect(); return { x: r.left + el.x, y: r.top + el.y }; })()"""))
    p.page.mouse.click(target["x"], target["y"])
    p.page.wait_for_function("!document.getElementById('view-drilldown').hidden")
    assert f"inst={target['id']}" in p.ev("location.hash")
    inst = next(i for i in load(DATA / "institutions.json")["institutions"] if i["inst_id"] == target["id"])
    assert p.page.locator("#inst-name").inner_text() == inst["name"]
    courses = [c for c in load(DATA / "courses.json")["courses"] if c["inst_id"] == target["id"]]
    shown = p.page.locator("#inst-detail td.pol .num").count()
    assert shown == sum(c["policy"] is not None for c in courses) > 0
    stmts = [s for s in load(DATA / "statements.json")["statements"] if s["inst_id"] == target["id"]]
    assert p.page.locator("#inst-detail .stmt").count() == len(stmts)
    assert "top decile" in p.page.locator("#inst-detail .inst-head").inner_text()
    caveat = p.page.locator("#gap-caveat").inner_text()
    assert "coding error" in caveat and "far from banning" in caveat
    assert p.errors == []
    p.page.close()


@pytest.mark.req("DASH-08")
def test_drilldown_picker_and_deep_link(browser, server):
    """The institution picker lists every institution; choosing one updates the URL, and loading that URL directly
    opens the same institution."""
    insts = load(DATA / "institutions.json")["institutions"]
    p = Page(browser, server)
    p.view("drilldown")
    assert p.page.locator("#inst-pick option").count() == len(insts)
    p.page.select_option("#inst-pick", "I010")
    p.page.wait_for_function("location.hash.includes('inst=I010')")
    name = next(i["name"] for i in insts if i["inst_id"] == "I010")
    assert p.page.locator("#inst-name").inner_text() == name
    p.page.close()
    q = Page(browser, server + "#view=drilldown&inst=I010")
    assert q.page.locator("#inst-name").inner_text() == name and q.errors == []
    q.page.close()


# ---------- DASH-06 ----------
@pytest.mark.req("DASH-06")
def test_keyboard_navigation_and_theme_toggle(browser, server):
    """Tabs are reachable by keyboard: arrow keys move between views and focus follows; table toggles are buttons
    that Enter activates. The theme toggle cycles auto -> light -> dark and redraws the charts without errors."""
    p = Page(browser, server)
    p.page.focus("#tab-summary")
    p.page.keyboard.press("ArrowRight")
    p.page.wait_for_function("document.getElementById('tab-policy').getAttribute('aria-selected') === 'true'")
    assert p.ev("location.hash") == "#view=policy"
    assert p.ev("document.activeElement.id") == "tab-policy"
    p.page.keyboard.press("End")
    p.page.wait_for_function("location.hash === '#view=drilldown'")
    p.page.keyboard.press("Home")
    p.page.wait_for_function("location.hash === '#view=summary'")
    p.view("policy")
    p.page.locator("#view-policy .table-toggle").first.focus()
    p.page.keyboard.press("Enter")
    assert p.page.locator("#view-policy .table-wrap").first.is_visible()
    bg = lambda: p.ev("getComputedStyle(document.body).backgroundColor")
    light = bg()
    p.page.click("#theme-toggle")  # auto -> light
    assert p.ev("document.documentElement.dataset.theme") == "light"
    p.page.click("#theme-toggle")  # light -> dark
    assert p.ev("document.documentElement.dataset.theme") == "dark" and bg() != light
    assert p.ev("Object.keys(window.__dash.charts).length") >= 5
    p.page.click("#theme-toggle")  # dark -> auto
    assert p.ev("document.documentElement.dataset.theme") is None
    assert p.errors == []
    p.page.close()


@pytest.mark.req("DASH-06")
def test_palettes_are_defined_for_both_themes():
    """Every color token is redefined for dark mode, both under the OS media query (guarded so a forced light
    theme wins) and under the explicit dark toggle; the categorical slots are the fixed-order reference palette."""
    css = (SITE / "dashboard" / "style.css").read_text(encoding="utf-8")
    root = re.search(r":root \{(.*?)\n\}", css, re.S).group(1)
    tokens = set(re.findall(r"(--[\w-]+):", root))
    media = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}', css, re.S).group(1)
    toggle = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', css, re.S).group(1)
    for block in (media, toggle):
        assert tokens <= set(re.findall(r"(--[\w-]+):", block))
    assert re.findall(r"--s\d: (#\w+)", root) == ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


# ---------- constraints from CLAUDE.md / DASH-01 ----------
@pytest.mark.req("DASH-01")
def test_cdn_libraries_pinned_and_no_build_step():
    """Every external script or stylesheet in the dashboard is loaded from an allowed CDN with an exact x.y.z
    version, and the dashboard is plain HTML/CSS/JS (no package.json, bundler config or module imports)."""
    html = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    urls = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert urls
    for u in urls:
        assert re.match(r"https://(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net/npm)/", u), u
        assert re.search(r"[/@]\d+\.\d+\.\d+/", u), f"not pinned to an exact version: {u}"
    assert not any((SITE / n).exists() for n in ["package.json", "vite.config.js", "webpack.config.js"])
    js = (SITE / "dashboard" / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|export)\s", js, re.M) and "require(" not in js


@pytest.mark.req("DASH-01")
def test_no_secrets_home_paths_or_emails_under_site():
    """No file under site/ contains an email address, an absolute home path, or a credential-looking string."""
    pats = [re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(r"/Users/|/home/\w|C:\\\\Users"),
            re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}"), re.compile(r"sk-[A-Za-z0-9]{20,}")]
    for f in SITE.rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            text = re.sub(r"https://cdn\.jsdelivr\.net/npm/[\w.-]+@\d+\.\d+\.\d+", "", text)  # npm pins use @
            for pat in pats:
                assert not pat.search(text), (f.relative_to(ROOT), pat.pattern)


# ---------- DASH-03 ----------
@pytest.mark.req("DASH-03")
def test_every_required_view_is_present_with_the_right_shape(page):
    """Each DASH-03 view exists with the expected structure: KPI tiles; policy by level as a 100% stacked bar
    (5 policy levels x 4 course levels); SE vs non-SE; trend over all 7 terms; a census-region comparison over the
    4 regions (no state map); a use x level heatmap (5 x 4); assessment by policy level (5 x 5); stance (5) and
    theme (3) prevalence; one scatter dot per institution in rhetoric.json; a coefficient plot with clustered and
    naive CIs per regression term; and the coder-accuracy panel (F1 and kappa)."""
    shape = page.ev("""Object.fromEntries(Object.entries(window.__dash.charts).map(([id, ch]) =>
        [id, { type: ch.config.type, stacked: !!(ch.options.scales.x && ch.options.scales.x.stacked),
               labels: ch.data.labels || [], sets: ch.data.datasets.map(d => [d.label, d.data.length]) }]))""")
    assert page.ev("document.querySelectorAll('#kpis .kpi').length") == 6
    assert shape["c-level"]["stacked"] and [n for _, n in shape["c-level"]["sets"]] == [4] * 5
    assert shape["c-se"]["labels"] == ["SE", "Non-SE"] and len(shape["c-se"]["sets"]) == 5
    assert shape["c-term"]["labels"] == load(RESULTS / "descriptives.json")["courses"]["term_order"]
    assert shape["c-region-policy"]["labels"] == shape["c-region-stance"]["labels"] == ["Northeast", "Midwest", "South", "West"]
    assert page.ev("document.body.textContent.includes('state map')") is False
    assert shape["c-heat"]["type"] == "matrix" and shape["c-heat"]["sets"][0][1] == 20
    assert shape["c-assess"]["stacked"] and [n for _, n in shape["c-assess"]["sets"]] == [5] * 5
    assert shape["c-stance"]["sets"][0][1] == 5 and shape["c-themes"]["sets"][0][1] == 3
    assert sum(n for _, n in shape["c-scatter"]["sets"]) == load(RESULTS / "rhetoric.json")["n_institutions"]
    n_terms = len(load(RESULTS / "regression.json")["coefficients"])
    labels = [l for l, _ in shape["c-coef"]["sets"]]
    assert any("clustered" in l for l in labels) and any("naive" in l for l in labels)
    assert all(n == n_terms for _, n in shape["c-coef"]["sets"])
    assert {"c-f1", "c-kappa"} <= set(shape)
