"""P1 generator tests: determinism (DATA-01) and real institution names from the reference list (DATA-02)."""
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
def test_reference_list_has_about_150_real_universities_with_states():
    """data/reference/real_universities.txt holds ~150 distinct real university names, each with a state that is
    a US postal code (or DC), in `Name | ST` form."""
    mod = gen_module()
    unis = mod.load_real_universities()
    assert 150 <= len(unis) <= 165
    assert len({n.casefold() for n, _ in unis}) == len(unis)
    states = {code for code, _ in mod.STATES} | {"DC"}
    assert not [(n, s) for n, s in unis if s not in states or not n]


@pytest.mark.req("DATA-02")
@pytest.mark.parametrize("seed", [2026, 1, 2, 3])
def test_every_name_is_from_the_real_list_with_no_duplicates(seed):
    """institutions.csv has 150 rows, every name is exactly an entry in the real list, and no name repeats."""
    rows = load(seed)["institutions"]
    assert len(rows) == 150
    names = [r["name"] for r in rows]
    assert len(set(names)) == 150
    real = set(gen_module().load_real_names())
    assert not [n for n in names if n not in real]


@pytest.mark.req("DATA-02")
@pytest.mark.parametrize("seed", [2026, 7])
def test_names_match_state_as_often_as_possible(seed):
    """'Matched by state where possible': the number of institutions whose name is a university in its own
    state equals the maximum possible, sum over states of min(institutions in state, names in state)."""
    from collections import Counter
    unis = dict(gen_module().load_real_universities())
    rows = load(seed)["institutions"]
    matched = sum(unis[r["name"]] == r["state"] for r in rows)
    have, avail = Counter(r["state"] for r in rows), Counter(unis.values())
    assert matched == sum(min(n, avail[s]) for s, n in have.items())
    assert matched > 75


@pytest.mark.req("DATA-02", "DATA-01")
def test_real_names_leave_every_other_column_and_table_unchanged():
    """Names are assigned by a separate seeded shuffle, so swapping them out changes no other column: rebuilding
    with the assignment disabled gives the same rows apart from the name."""
    mod = gen_module()
    real = mod.build(2026)
    orig = mod.assign_real_names
    try:
        mod.assign_real_names = lambda rows, unis, seed: rows
        plain = mod.build(2026)
    finally:
        mod.assign_real_names = orig
    strip = lambda rows: [{k: v for k, v in r.items() if k != "name"} for r in rows]
    assert strip(real["institutions"]) == strip(plain["institutions"])
    for key in ("statements", "courses", "ground_truth"):
        assert real[key] == plain[key], key


@pytest.mark.req("DATA-02")
def test_too_short_a_list_is_an_error():
    """With fewer distinct real names than institutions the generator raises instead of repeating a name."""
    mod = gen_module()
    with pytest.raises(ValueError, match="distinct real names"):
        mod.assign_real_names([{"state": "CA"}] * 3, [("A", "CA"), ("B", "CA")], 1)


@pytest.mark.req("DATA-02")
def test_institution_columns():
    """institutions.csv has exactly the DATA-02 columns, in order."""
    header = list(load(2026)["institutions"][0].keys())
    assert header == ["inst_id", "name", "state", "census_region", "control", "carnegie",
                      "cs_enrollment"]
