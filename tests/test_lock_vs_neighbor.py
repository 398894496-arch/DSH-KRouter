from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures/lock_vs_neighbor"))

from run import run


def test_lock_never_returns_a_neighbor_on_this_fixture():
    result = run()
    k = result["systems"]["krouter"]
    assert k["false_neighbor"] == 0
    assert k["slices"]["hit"]["exact"] == 1.0
    assert k["slices"]["supersede"]["old_page"] == 0
    assert k["slices"]["supersede"]["exact"] == 1.0
    assert k["slices"]["negative"]["exact"] == 1.0


def test_vector_and_lexical_prefer_the_superseded_page():
    result = run()
    for name in ("lexical", "tfidf", "hybrid"):
        sl = result["systems"][name]["slices"]["supersede"]
        assert sl["old_page"] == 1.0, name
        assert sl["exact"] == 0.0, name


def test_tfidf_false_neighbor_rate_is_higher_than_the_lock():
    result = run()
    k = result["systems"]["krouter"]["false_neighbor"]
    v = result["systems"]["tfidf"]["false_neighbor"]
    assert v > k


def test_krouter_is_deterministic_on_this_map():
    a = run()
    b = run()
    assert a["systems"]["krouter"]["cases"] == b["systems"]["krouter"]["cases"]
