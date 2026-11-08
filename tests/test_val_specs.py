"""VAL-03: requirement lines are parsed from specs/*.md, and every test tag names a real requirement."""
import re

import pytest

import conftest
from hookutil import ROOT
from src.validation import specs


@pytest.mark.req("VAL-03")
def test_parser_finds_every_requirement_bullet():
    """Every `- **AREA-NN**` bullet in specs/*.md is parsed once, IDs are unique, and the
    total is the 75 requirements of P0-P7."""
    reqs = specs.requirements()
    raw = re.findall(r"^- \*\*([A-Z]+-\d{2})\*\*", "\n".join(
        p.read_text() for p in sorted((ROOT / "specs").glob("*.md"))), flags=re.M)
    assert [r["id"] for r in reqs] == raw
    assert len(reqs) == 75
    counts = {}
    for r in reqs:
        counts[r["phase"]] = counts.get(r["phase"], 0) + 1
    assert counts == {"P0": 9, "P1": 17, "P2": 14, "P3": 8, "P4": 8, "P5": 6, "P6": 8, "P7": 5}


@pytest.mark.req("VAL-03")
def test_requirement_text_keeps_wrapped_lines_and_nested_bullets(tmp_path):
    """Wrapped lines join the requirement text; nested bullets stay on their own lines; a
    blank line or a non-indented line ends the requirement; duplicate IDs are an error."""
    (tmp_path / "a.md").write_text(
        "# T\n- **ABC-01** first\n  wrapped\n  - sub one\n\nprose\n- **ABC-02** second\nnot part\n")
    reqs = specs.requirements(tmp_path)
    assert [(r["id"], r["text"]) for r in reqs] == [("ABC-01", "first wrapped\n- sub one"), ("ABC-02", "second")]
    r = {x["id"]: x for x in specs.requirements()}
    assert "SessionEnd: payload.reason" in r["INST-02"]["text"]
    assert "Uncaught faults are listed, not hidden." in r["VAL-04"]["text"]
    (tmp_path / "b.md").write_text("- **ABC-01** again\n")
    with pytest.raises(ValueError, match="ABC-01"):
        specs.requirements(tmp_path)


@pytest.mark.req("VAL-03")
def test_every_req_tag_names_a_spec_requirement(request):
    """Every @pytest.mark.req ID on a collected test exists in a spec, so the traceability
    matrix can't silently drop a test. The plugin and the parser map areas to the same phases."""
    known = {r["id"] for r in specs.requirements()}
    used = {rid for item in request.session.items for m in item.iter_markers("req") for rid in m.args}
    assert used and used <= known, sorted(used - known)
    assert conftest.PHASE_BY_AREA == specs.PHASE_BY_AREA
