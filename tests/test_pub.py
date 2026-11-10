"""PUB-01..05: the landing page, the Pages workflow, the pre-publish gate, the README and the evaluation page.

Pages are served from site/ over HTTP and checked in headless Chromium. The evaluation page loads marked and
DOMPurify from their pinned CDN URLs, so its browser tests need the network, like the validation explorer's.
"""
import functools
import http.server
import json
import re
import shutil
import subprocess
import threading
from html.parser import HTMLParser

import pytest
from playwright.sync_api import sync_playwright

from hookutil import ROOT
from src.publish import prepublish as P

SITE = ROOT / "site"
REPO = "https://github.com/aayushkeshari/genai-cs-policy"
LIVE = "https://aayushkeshari.github.io/genai-cs-policy/"
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.scripts = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])


def links(path):
    p = _Links()
    p.feed(path.read_text(encoding="utf-8"))
    return p


def make_n(target):
    return subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True, text=True, timeout=30)


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


def fake_site(tmp_path, page_html, extra=None):
    """A one-page site in tmp_path for exercising the prepublish checks."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(page_html, encoding="utf-8")
    for name, text in (extra or {}).items():
        f = site / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return site


GOOD = '<html><body><p id="synthetic-banner">Synthetic data — illustrative.</p>{}</body></html>'


# ---------------------------------------------------------------- PUB-01

@pytest.mark.req("PUB-01")
def test_landing_page_links_every_page_and_the_repo():
    """site/index.html links the dashboard, validation explorer, timeline, tokens page, evaluation page and the
    GitHub repo, and every local link points at a page that exists."""
    hrefs = links(SITE / "index.html").hrefs
    for target in ["dashboard/", "validation/", "timeline/", "tokens/", "evaluation/", REPO]:
        assert target in hrefs, target
    for h in hrefs:
        if not h.startswith(("http", "#")):
            assert (SITE / h / "index.html").is_file(), h


@pytest.mark.req("PUB-01")
def test_every_page_links_back_to_the_landing_page():
    """Each section page has an 'All pages' link to ../, so a visitor can always get back to the landing page."""
    for name in ["dashboard", "validation", "timeline", "tokens", "evaluation"]:
        assert "../" in links(SITE / name / "index.html").hrefs, name


@pytest.mark.req("PUB-01")
@pytest.mark.parametrize("width", [375, 1280])
def test_landing_page_renders_and_navigates(browser, server, width):
    """In a real browser the landing page shows the synthetic banner and six cards with no horizontal scroll (phone
    and desktop), and clicking the Tokens card opens the token page."""
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server)
    assert "Synthetic data" in page.inner_text("#synthetic-banner")
    assert page.locator("#pages .card").count() == 6
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.click("a.card[href='tokens/']")
    page.wait_for_url(re.compile(r"/tokens/$"))
    assert page.title() == "Token Usage"
    assert not errors, errors
    page.close()


# ---------------------------------------------------------------- PUB-02

@pytest.mark.req("PUB-02")
def test_pages_workflow_deploys_site_on_push_to_main():
    """.github/workflows/pages.yml runs on push to main, has the Pages permissions, uploads site/ as the Pages
    artifact and deploys it with actions/deploy-pages. Every action is pinned to a version tag."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"on:\s*\n\s+push:\s*\n\s+branches:\s*\[main\]", text)
    for perm in ["pages: write", "id-token: write"]:
        assert perm in text
    assert re.search(r"uses: actions/upload-pages-artifact@v\d+\s*\n\s+with:\s*\n\s+path: site\s*$", text, re.M)
    assert re.search(r"uses: actions/deploy-pages@v\d+", text)
    uses = re.findall(r"uses:\s*(\S+)", text)
    assert uses and all(re.fullmatch(r"actions/[\w-]+@v\d+(\.\d+)*", u) for u in uses), uses


@pytest.mark.req("PUB-02")
def test_site_uses_only_relative_links_so_it_works_under_the_pages_subpath():
    """The site is served from /genai-cs-policy/, so no page may use a root-absolute link like /dashboard/."""
    for page in P.html_pages():
        for h in links(page).hrefs + links(page).scripts:
            assert not (h.startswith("/") and not h.startswith("//")), f"{page}: {h}"


# ---------------------------------------------------------------- PUB-03

@pytest.mark.req("PUB-03")
def test_prepublish_target_runs_tests_then_the_checks():
    """`make prepublish` builds the site, runs the full test suite, then runs the redaction, link and banner checks."""
    cmds = make_n("prepublish").stdout
    assert "cp docs/evaluation.md site/evaluation/evaluation.md" in cmds
    assert "pytest" in cmds
    assert cmds.index("pytest") < cmds.index("src.publish.prepublish")


@pytest.mark.req("PUB-03")
def test_committed_site_passes_every_check():
    """The site as committed has no redaction problems, no broken links and a synthetic banner on every page."""
    assert P.run() == []
    assert len(P.html_pages()) >= 6


@pytest.mark.req("PUB-03")
@pytest.mark.parametrize("leak", ["/Users/someone/project/file.py", "/home/runner/x", "a.person@example.org",
                                  'api_key = "abcdefghijkl"', "sk-" + "A" * 24],
                         ids=["mac-home", "linux-home", "email", "api-key", "sk-key"])  # leak-free IDs survive redaction
@pytest.mark.parametrize("where", ["html", "json"])
def test_redaction_scan_catches_each_leak_class(tmp_path, leak, where):
    """A home path, an email, a credential assignment or an sk- key anywhere in a page or a JSON data file fails the
    scan. In JSON the leak is found inside decoded strings."""
    if where == "html":
        site = fake_site(tmp_path, GOOD.format(f"<p>{leak}</p>"))
    else:
        site = fake_site(tmp_path, GOOD.format(""), {"data/x.json": json.dumps({"rows": [{"text": leak}]})})
    assert any(p.startswith("redaction:") for p in P.run(site))


@pytest.mark.req("PUB-03")
def test_redaction_scan_ignores_known_lookalikes(tmp_path):
    """A pinned npm CDN URL (name@2.0.1), a JSON-escaped newline before a decorator, and already-redacted placeholders
    are not leaks."""
    page = GOOD.format('<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2.0.1/dist/m.min.js"></script>'
                       "<p>‹redacted-email› ‹redacted-path›</p>")
    site = fake_site(tmp_path, page, {"data/t.json": json.dumps({"source": '@pytest.mark.req("A")\n@pytest.mark.x'})})
    assert P.run(site) == []


@pytest.mark.req("PUB-03")
@pytest.mark.parametrize("bad, expect", [
    ('<a href="missing/">x</a>', "does not exist"),
    ('<link rel="stylesheet" href="nope.css">', "does not exist"),
    ('<a href="/dashboard/">x</a>', "root-absolute"),
    ('<a href="../outside.html">x</a>', "outside site/"),
    ('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', "unpinned"),
    ('<script src="http://cdnjs.cloudflare.com/ajax/libs/x/1.2.3/x.js"></script>', "insecure"),
])
def test_link_check_catches_bad_links(tmp_path, bad, expect):
    """Each kind of broken or unsafe link is reported: missing local targets, root-absolute paths (they break under
    the Pages subpath), paths leaving site/, unpinned libraries and plain http."""
    (tmp_path / "outside.html").write_text("x", encoding="utf-8")
    problems = P.link_problems(fake_site(tmp_path, GOOD.format(bad)))
    assert any(expect in p for p in problems), problems


@pytest.mark.req("PUB-03")
def test_link_check_accepts_good_links(tmp_path):
    """Directory links resolve to their index.html, fragments are allowed, and pinned https libraries pass."""
    page = GOOD.format('<a href="sub/">s</a><a href="#top">t</a><a href="sub/index.html#x">x</a>'
                       '<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>')
    site = fake_site(tmp_path, page, {"sub/index.html": GOOD.format("")})
    assert P.link_problems(site) == []


@pytest.mark.req("PUB-03")
@pytest.mark.parametrize("html, expect", [
    ("<html><body><p>no banner</p></body></html>", "has no #synthetic-banner"),
    ('<html><body><p id="synthetic-banner">Real data</p><p>Synthetic data</p></body></html>', "does not say"),
])
def test_banner_check_catches_missing_or_wrong_banner(tmp_path, html, expect):
    """A page without #synthetic-banner, or whose banner doesn't say 'Synthetic data' (text elsewhere doesn't
    count), fails."""
    problems = P.banner_problems(fake_site(tmp_path, html))
    assert len(problems) == 1 and expect in problems[0], problems


@pytest.mark.req("PUB-03")
def test_prepublish_exit_status(tmp_path, monkeypatch, capsys):
    """main() returns 0 and prints OK on a clean site, and returns 1 and lists each problem on a bad one."""
    monkeypatch.setattr(P, "SITE", fake_site(tmp_path, GOOD.format("")))
    monkeypatch.setattr(P.run, "__defaults__", (P.SITE,))
    monkeypatch.setattr(P.html_pages, "__defaults__", (P.SITE,))
    assert P.main() == 0 and "prepublish: OK" in capsys.readouterr().out
    (P.SITE / "index.html").write_text("<p>no banner</p>", encoding="utf-8")
    assert P.main() == 1
    out = capsys.readouterr().out
    assert "banner: index.html has no #synthetic-banner" in out and "FAILED" in out


# ---------------------------------------------------------------- PUB-04

@pytest.mark.req("PUB-04")
def test_readme_explains_project_reproduction_and_live_url():
    """README.md says the data is synthetic, gives the live URL and every page, tells how to reproduce with
    `make all`, and names the Pages setting to change."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert LIVE in text and "synthetic" in text.lower()
    for page in ["dashboard/", "validation/", "timeline/", "tokens/", "evaluation/"]:
        assert LIVE + page in text, page
    assert "make all" in text and "make setup" in text and "make prepublish" in text
    assert "Source" in text and "GitHub Actions" in text
    assert not re.search(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", text) and "/Users/" not in text


@pytest.mark.req("PUB-04")
def test_make_all_runs_the_whole_pipeline():
    """`make all` runs data, analysis, report, timeline, tokens (only when raw_logs/ exists), site and test, in that
    order."""
    cmds = make_n("all").stdout
    steps = ["generate.py", "src.analysis.run", "src.report.build_site_data", "src.provenance.build_timeline",
             "raw_logs/transcripts", "cp docs/evaluation.md", "pytest"]
    idx = [cmds.find(s) for s in steps]
    assert -1 not in idx and idx == sorted(idx), dict(zip(steps, idx))


@pytest.mark.req("PUB-04")
def test_make_all_skips_tokens_without_raw_logs(tmp_path):
    """On a fresh clone (no raw_logs/), the guard in `make all` skips `make tokens` instead of overwriting the
    committed results/tokens.json with an empty build."""
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    guard = next(l for l in mk.splitlines() if "raw_logs/transcripts" in l and "$(MAKE) tokens" in l)
    shell = guard.strip().lstrip("@").replace("$(MAKE) tokens", "echo RAN-TOKENS")
    out = subprocess.run(["sh", "-c", shell], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "skipped" in out and "RAN-TOKENS" not in out
    (tmp_path / "raw_logs" / "transcripts").mkdir(parents=True)
    out = subprocess.run(["sh", "-c", shell], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "RAN-TOKENS" in out


# ---------------------------------------------------------------- PUB-05

@pytest.mark.req("PUB-05")
def test_published_evaluation_is_a_byte_copy_of_the_doc():
    """site/evaluation/evaluation.md is byte-for-byte docs/evaluation.md, so the page shows Aayush's text unedited."""
    assert (SITE / "evaluation" / "evaluation.md").read_bytes() == (ROOT / "docs" / "evaluation.md").read_bytes()


@pytest.mark.req("PUB-05")
@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_agent_commit_ever_changed_the_evaluation():
    """git history shows that docs/evaluation.md was only ever changed by human commits, never by an `agent:` one."""
    subjects = subprocess.run(["git", "log", "--format=%s", "--", "docs/evaluation.md"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.splitlines()
    assert subjects and not [s for s in subjects if s.startswith("agent:")], subjects


@pytest.mark.req("PUB-05")
def test_evaluation_page_renders_the_markdown(browser, server):
    """In a real browser the evaluation page renders the doc's heading, the goals table (G1..G5 rows) and the
    reflection heading, under the synthetic banner."""
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}evaluation/")
    page.wait_for_selector("#evaluation h1", timeout=20000)
    md = (ROOT / "docs" / "evaluation.md").read_text(encoding="utf-8")
    assert page.inner_text("#evaluation h1") == re.search(r"^# (.+)$", md, re.M).group(1)
    assert page.locator("#evaluation table tbody tr").count() == len(re.findall(r"^\| G\d", md, re.M))
    assert "Reflection" in page.inner_text("#evaluation")
    assert "Synthetic data" in page.inner_text("#synthetic-banner")
    assert not errors, errors
    page.close()


@pytest.mark.req("PUB-05")
def test_evaluation_page_sanitizes_and_reports_errors(browser, server):
    """Script-bearing HTML in the doc is sanitized (no handler survives), and a missing file shows an error message
    instead of a blank page."""
    page = browser.new_page()
    page.route("**/evaluation/evaluation.md",
               lambda r: r.fulfill(status=200, body="# T\n\n<img src=x onerror=\"window.__x=1\">"))
    page.goto(f"{server}evaluation/")
    page.wait_for_selector("#evaluation h1", timeout=20000)
    assert page.evaluate("window.__x") is None
    assert page.locator("#evaluation [onerror]").count() == 0
    page.close()
    page = browser.new_page()
    page.route("**/evaluation/evaluation.md", lambda r: r.fulfill(status=404, body="no"))
    page.goto(f"{server}evaluation/")
    page.wait_for_selector("#load-error:not([hidden])", timeout=20000)
    assert "HTTP 404" in page.inner_text("#load-error")
    page.close()


@pytest.mark.req("PUB-05")
def test_evaluation_page_libraries_are_pinned():
    """The page's only external scripts are marked 12.0.2 and DOMPurify 3.1.6 at exact-version cdnjs URLs."""
    ext = [s for s in links(SITE / "evaluation" / "index.html").scripts if s.startswith("http")]
    assert ext == ["https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js",
                   "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js"]
