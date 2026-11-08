"""Parse requirement lines from specs/*.md (VAL-03).

A requirement starts with a bullet `- **AREA-NN** text`. Indented lines that follow are part of its
text: wrapped lines join with a space, nested bullets keep their own line.
"""
import re
from pathlib import Path

SPECS = Path(__file__).resolve().parents[2] / "specs"
REQ_LINE = re.compile(r"^- \*\*([A-Z]+-\d{2})\*\*\s*(.*)$")
PHASE_BY_AREA = {"INST": "P0", "DATA": "P1", "ANL": "P2", "DASH": "P3",
                 "VAL": "P4", "PROV": "P5", "TOK": "P6", "PUB": "P7"}


def parse_spec(path: Path) -> list[dict]:
    reqs, current = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = REQ_LINE.match(line)
        if m:
            current = {"id": m.group(1), "phase": PHASE_BY_AREA.get(m.group(1).split("-")[0], "untagged"),
                       "spec": Path(path).name, "text": m.group(2).strip()}
            reqs.append(current)
        elif current and line.startswith((" ", "\t")) and line.strip():
            sub = line.lstrip().startswith("- ")  # a nested bullet keeps its own line
            current["text"] += ("\n" if sub else " ") + line.strip()
        else:
            current = None
    return reqs


def requirements(specs_dir: Path = SPECS) -> list[dict]:
    """Every requirement in every spec, in file then line order. IDs are unique (ValueError otherwise)."""
    out = [r for p in sorted(Path(specs_dir).glob("*.md")) for r in parse_spec(p)]
    ids = [r["id"] for r in out]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate requirement IDs: {dupes}")
    return out
