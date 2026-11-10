"""PUB-03: the checks `make prepublish` runs on site/ after the test suite passes.

1. Redaction scan: no text file under site/ contains a home path, an email address or a credential-like
   string (the same rules as src/validation/redact.py). Already-redacted placeholders pass.
2. Link check: every local href/src in every HTML page resolves to a file in site/. External scripts and
   stylesheets must be https and pinned to an exact x.y.z version. External links are not fetched, so the
   check is offline and deterministic.
3. Banner: every HTML page under site/ has a #synthetic-banner element that says "Synthetic data".

Exit status is 0 when all three pass, 1 otherwise. Each problem is printed on its own line.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from src.validation.redact import RULES

# The redaction rules, except that an email needs an alphabetic top-level domain, so a pinned CDN URL
# such as chartjs-chart-matrix@2.0.1 is not mistaken for an address.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")
SCAN = [pat for pat, _ in RULES if "@" not in pat.pattern] + [EMAIL]

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md", ".txt", ".svg"}
PINNED = re.compile(r"(?:/|@)\d+\.\d+\.\d+(?:/|$)")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[tuple[str, str, str]] = []  # (tag, attr, url)
        self.banner_depth = 0
        self.banner_text = ""
        self.has_banner = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for attr in ("href", "src"):
            if a.get(attr):
                self.refs.append((tag, attr, a[attr]))
        if tag in {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}:
            return
        self._depth += 1
        if a.get("id") == "synthetic-banner":
            self.has_banner = True
            self.banner_depth = self._depth

    def handle_endtag(self, tag):
        if self.banner_depth and self._depth == self.banner_depth:
            self.banner_depth = 0
        self._depth -= 1

    def handle_data(self, data):
        if self.banner_depth:
            self.banner_text += data


def _parse(path: Path) -> _Page:
    p = _Page()
    p.feed(path.read_text(encoding="utf-8"))
    return p


def html_pages(site: Path = SITE) -> list[Path]:
    return sorted(site.rglob("*.html"))


def leaks(text: str) -> list[str]:
    """Substrings of text that look like a home path, an email address or a secret."""
    return [m.group(0) for pat in SCAN for m in pat.finditer(text)]


def _strings(obj):
    """Every key and string value in decoded JSON, so escapes like '\\n' are not read as text."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def redaction_problems(site: Path = SITE) -> list[str]:
    out = []
    for f in sorted(site.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        chunks = list(_strings(json.loads(text))) if f.suffix.lower() == ".json" else text.splitlines()
        for chunk in chunks:
            for hit in leaks(chunk):
                out.append(f"redaction: {f.relative_to(site)} contains {hit[:12]}… (home path, email or secret)")
    return out


def link_problems(site: Path = SITE) -> list[str]:
    out = []
    for page in html_pages(site):
        rel = page.relative_to(site)
        for tag, attr, url in _parse(page).refs:
            parts = urlsplit(url)
            if parts.scheme in {"http", "https"}:
                if parts.scheme == "http":
                    out.append(f"link: {rel} uses insecure {url}")
                if (tag == "script" or (tag == "link" and attr == "href")) and parts.netloc != "fonts.googleapis.com" \
                        and not PINNED.search(parts.path):
                    out.append(f"link: {rel} loads an unpinned library {url}")
                continue
            if parts.scheme in {"mailto", "javascript", "data"} or url.startswith("#"):
                if parts.scheme == "mailto":
                    out.append(f"link: {rel} has a mailto link")
                continue
            if url.startswith("/"):
                out.append(f"link: {rel} uses root-absolute {url} (breaks under the Pages subpath)")
                continue
            target = (page.parent / unquote(parts.path)).resolve()
            if url.endswith("/") or target.is_dir():
                target = target / "index.html"
            try:
                target.relative_to(site.resolve())
            except ValueError:
                out.append(f"link: {rel} points outside site/: {url}")
                continue
            if not target.is_file():
                out.append(f"link: {rel} -> {url} does not exist")
    return out


def banner_problems(site: Path = SITE) -> list[str]:
    out = []
    for page in html_pages(site):
        p = _parse(page)
        if not p.has_banner:
            out.append(f"banner: {page.relative_to(site)} has no #synthetic-banner")
        elif "synthetic data" not in p.banner_text.lower():
            out.append(f"banner: {page.relative_to(site)} banner does not say 'Synthetic data'")
    return out


def run(site: Path = SITE) -> list[str]:
    return redaction_problems(site) + link_problems(site) + banner_problems(site)


def main() -> int:
    problems = run()
    for p in problems:
        print(p)
    pages = len(html_pages())
    if problems:
        print(f"prepublish: FAILED with {len(problems)} problem(s) across {pages} pages")
        return 1
    print(f"prepublish: OK ({pages} pages: redaction clean, links resolve, synthetic banner on every page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
