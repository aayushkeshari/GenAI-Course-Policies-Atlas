"""P1 generator tests: determinism (DATA-01) and fictional institution names (DATA-02)."""
import pytest

from datautil import FILES, ROOT, gen_module, generated_dir, load, read_csv


def _bytes(d):
    return {f: (d / f).read_bytes() for f in FILES if (d / f).exists()}


@pytest.mark.req("DATA-01")
def test_same_seed_gives_byte_identical_files(tmp_path):
    """Generating twice with seed 2026 into two separate directories gives byte-identical files,
    for every output file."""
    a, b = tmp_path / "a", tmp_path / "b"
    gen_module().generate(2026, a)
    gen_module().generate(2026, b)
    ba, bb = _bytes(a), _bytes(b)
    assert ba and ba.keys() == bb.keys()
    for f in ba:
        assert ba[f] == bb[f], f"{f} differs between two runs with the same seed"


@pytest.mark.req("DATA-01")
def test_different_seed_gives_different_data():
    """A different seed changes the data, so the seed actually drives generation."""
    assert _bytes(generated_dir(2026))["institutions.csv"] != _bytes(generated_dir(7))["institutions.csv"]


@pytest.mark.req("DATA-01")
def test_cli_accepts_seed_flag(tmp_path):
    """`generate.py --seed N --out DIR` writes the files and matches the library call."""
    gen_module().main(["--seed", "2026", "--out", str(tmp_path)])
    assert _bytes(tmp_path) == _bytes(generated_dir(2026))


@pytest.mark.req("DATA-02")
def test_reference_list_has_about_150_real_universities():
    """data/reference/real_universities.txt holds ~150 distinct real university names."""
    names = gen_module().load_real_names()
    assert 135 <= len(names) <= 165
    assert len({n.casefold() for n in names}) == len(names)


@pytest.mark.req("DATA-02")
@pytest.mark.parametrize("seed", [2026, 1, 2, 3])
def test_institutions_have_150_unique_fictional_names(seed):
    """institutions.csv has 150 rows, unique names, and no name equals any real university
    name (compared case-insensitively, which is stricter than the spec's exact match)."""
    rows = load(seed)["institutions"]
    assert len(rows) == 150
    names = [r["name"] for r in rows]
    assert len({n.casefold() for n in names}) == 150
    real = {n.casefold() for n in gen_module().load_real_names()}
    assert not [n for n in names if n.casefold() in real]


@pytest.mark.req("DATA-02")
def test_generator_rejects_names_on_the_real_list(monkeypatch):
    """If a word-list combination is on the real list, the generator rejects it and draws again:
    with a real list containing every name seed 2026 would produce, none of them are used."""
    mod = gen_module()
    first = [r["name"] for r in mod.build(2026)["institutions"]]
    monkeypatch.setattr(mod, "load_real_names", lambda: first)
    second = [r["name"] for r in mod.build(2026)["institutions"]]
    assert not set(n.casefold() for n in second) & set(n.casefold() for n in first)


@pytest.mark.req("DATA-02")
def test_institution_columns():
    """institutions.csv has exactly the DATA-02 columns, in order."""
    header = list(load(2026)["institutions"][0].keys())
    assert header == ["inst_id", "name", "state", "census_region", "control", "carnegie",
                      "cs_enrollment"]
