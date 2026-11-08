"""Scrub published test text (sources, docstrings, failure messages, node IDs) for site/ (CLAUDE.md:
no secrets, absolute home paths or emails under site/).

Some tests deliberately contain fake home paths, fake tokens and email-shaped strings as fixtures (e.g. the
redaction tests). Those are replaced with visible placeholders, never silently dropped, and the explorer
says that published test text is redacted.
"""
import re
from pathlib import Path

HOME = str(Path.home())
RULES = [
    (re.compile(re.escape(HOME)), "~"),
    (re.compile(r"(?:/Users/|/home/(?=\w)|C:\\+Users)[^\s'\"\]\),;`]*"), "‹redacted-path›"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "‹redacted-email›"),
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[:=]\s*)['\"][^'\"]{8,}['\"]?"), r"\1‹redacted-secret›"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "‹redacted-secret›"),
]


def scrub(text: str) -> str:
    for pat, repl in RULES:
        text = pat.sub(repl, text)
    return text
