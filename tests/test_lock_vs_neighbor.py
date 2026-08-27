from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures/lock_vs_neighbor"))

from run import run


def test_lock_never_returns_a_neighbor_on_this_fixture():
    result = run()
    k = result["systems"]["krouter"]
    assert k["n"] == 22
    assert k["false_neighbor"] == 0
    assert k["slices"]["hit"]["n"] == 10
    assert k["slices"]["supersede"]["n"] == 4
    assert k["slices"]["neighbor"]["n"] == 4
    assert k["slices"]["negative"]["n"] == 4
    assert k["slices"]["hit"]["exact"] == 1.0
    assert k["slices"]["supersede"]["old_page"] == 0
    assert k["slices"]["supersede"]["exact"] == 1.0
    assert k["slices"]["negative"]["exact"] == 1.0


def test_naive_vector_prefers_the_superseded_page():
    """No metadata: cosine over every file, including invalid_at."""
    result = run()
    for name in ("lexical", "tfidf", "hybrid"):
        sl = result["systems"][name]["slices"]["supersede"]
        assert sl["old_page"] == 1.0, name
        assert sl["exact"] == 0.0, name


def test_metadata_ablation_closes_the_supersede_gap():
    """Same invalid_at filter as the lock. Old page gone; cosine hits the live page."""
    result = run()
    for name in ("lexical_live", "tfidf_live", "tfidf_map", "hybrid_live"):
        sl = result["systems"][name]["slices"]["supersede"]
        assert sl["old_page"] == 0, name
        assert sl["exact"] == 1.0, name


def test_after_ablation_unthresholded_cosine_does_not_refuse():
    """Same live map, no similarity floor: cosine always returns a page on the 4 negatives."""
    result = run()
    k = result["systems"]["krouter"]
    mapped = result["systems"]["tfidf_map"]
    assert k["slices"]["negative"]["n"] == 4
    assert mapped["slices"]["negative"]["miss"] == 0
    assert k["slices"]["negative"]["miss"] == 1.0


def test_no_tfidf_map_threshold_matches_the_lock_on_this_fixture():
    """A floor high enough to refuse all 4 negatives also drops a true CJK hit."""
    result = run()
    assert result["threshold_curve"]
    assert result["threshold_any_matches_lock"] is False
    # Unthresholded point is in the curve.
    zero = result["threshold_curve"][0]
    assert zero["min_score"] == 0.0
    assert zero["negative_miss"] == 0


def test_krouter_is_deterministic_on_this_map():
    a = run()
    b = run()
    assert a["systems"]["krouter"]["cases"] == b["systems"]["krouter"]["cases"]
