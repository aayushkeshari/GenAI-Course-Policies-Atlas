"""ANL-10 (methods.md) and ANL-14's documentation clause (methods.md states the method for each result)."""
import re

import pytest

from src.analysis.common import ROOT

METHODS = ROOT / "docs" / "methods.md"


def text():
    return METHODS.read_text(encoding="utf-8")


@pytest.mark.req("ANL-10")
def test_methods_says_synthetic_up_front():
    """methods.md states, before the first section, that all data is synthetic and the results describe the
    generator, not real departments."""
    head = text().split("\n## ", 1)[0]
    assert "SYNTHETIC" in head and "not real" in head


@pytest.mark.req("ANL-10")
def test_methods_covers_every_analysis_and_the_limits():
    """methods.md covers cleaning, coding, clustering, the analyses, the recovery checks, and a limits section
    with subsections on synthetic data, keyword coding, and methods."""
    t = text()
    for req in ["ANL-01", "ANL-02", "ANL-03", "ANL-04", "ANL-05", "ANL-06", "ANL-07", "ANL-08", "ANL-11", "ANL-12", "ANL-13", "ANL-14"]:
        assert req in t, req
    limits = t.split("## 6. Limits", 1)[1]
    for part in ["Of synthetic data", "Of keyword coding", "Of the methods"]:
        assert part in limits


@pytest.mark.req("ANL-14")
@pytest.mark.req("ANL-10")
@pytest.mark.parametrize("result", ["descriptives", "allowed_uses", "assessment", "association", "regression", "rhetoric", "recovery"])
def test_methods_states_inference_method_for_each_result(result):
    """The clustering table in methods.md has a row for each inferential results file, naming its method
    (cluster bootstrap, cluster-robust SEs, or bootstrap over institutions)."""
    table = text().split("## 3. Why clustering matters", 1)[1].split("\n## ", 1)[0]
    row = next((l for l in table.splitlines() if f"`results/{result}.json`" in l), None)
    assert row, result
    assert re.search(r"cluster bootstrap|cluster-robust|bootstrap over institutions|clustered regression", row), row


@pytest.mark.req("ANL-10")
def test_methods_has_no_hardcoded_result_numbers():
    """methods.md does not quote estimates (decimals like 0.83), so it cannot drift from results/; numbers
    live only in results/*.json."""
    assert not re.findall(r"\b\d\.\d{2,}\b", text())


@pytest.mark.req("ANL-10")
def test_methods_documents_the_far_from_negation_limit():
    """The known coder error found in P3 is documented as a limitation: the "far from banning" negation is
    coded prohibitive, it was left unfixed because dev has no such wording (fixing it would tune on held-out),
    and rhetoric-gap institutions may reflect coding errors."""
    t = text()
    limits = t[t.index("## 6. Limits"):]
    for phrase in ["Far from banning", "S-2-ban", "tuning on held-out", "coding errors"]:
        assert phrase in limits, phrase
