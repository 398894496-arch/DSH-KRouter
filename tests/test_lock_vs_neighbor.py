from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent / "fixtures/lock_vs_neighbor"
_spec = importlib.util.spec_from_file_location("lock_vs_neighbor_run", HERE / "run.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
load_gold = _mod.load_gold
run = _mod.run
DEFAULT_GOLD = _mod.DEFAULT_GOLD


GOLD = load_gold(DEFAULT_GOLD)
N_HIT = sum(1 for item in GOLD if item["slice"] == "hit")
N_SUPERSEDE = sum(1 for item in GOLD if item["slice"] == "supersede")
N_NEIGHBOR = sum(1 for item in GOLD if item["slice"] == "neighbor")
N_NEGATIVE = sum(1 for item in GOLD if item["slice"] == "negative")
N_REWRITE = sum(1 for item in GOLD if item.get("kind") == "rewrite")
N = len(GOLD)


def test_lock_never_returns_a_neighbor_on_this_fixture():
    result = run()
    k = result["systems"]["krouter"]
    assert k["n"] == N
    assert k["false_neighbor"] == 0
    assert k["slices"]["hit"]["n"] == N_HIT
    assert k["slices"]["supersede"]["n"] == N_SUPERSEDE
    assert k["slices"]["neighbor"]["n"] == N_NEIGHBOR
    assert k["slices"]["negative"]["n"] == N_NEGATIVE
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
    """Same live map, no similarity floor: cosine always returns a page on the negatives."""
    result = run()
    k = result["systems"]["krouter"]
    mapped = result["systems"]["tfidf_map"]
    assert k["slices"]["negative"]["n"] == N_NEGATIVE
    assert N_NEGATIVE >= 12
    assert mapped["slices"]["negative"]["miss"] == 0
    assert k["slices"]["negative"]["miss"] == 1.0


def test_no_tfidf_map_threshold_matches_the_lock_on_this_fixture():
    """Lexical TF-IDF: no floor keeps every hit and refuses every negative."""
    result = run()
    assert result["threshold_curve"]
    assert result["threshold_any_matches_lock"] is False
    zero = result["threshold_curve"][0]
    assert zero["min_score"] == 0.0
    assert zero["negative_miss"] == 0


def test_rewrite_inversion_is_not_one_pair():
    """CJK rewrite hits on six pages sit below the strongest OOD negative."""
    result = run()
    hinge = result["hinge"]
    assert N_REWRITE >= 6
    assert hinge["n_inverted_rewrite"] >= 5
    pages = {row["gold"] for row in hinge["inverted_rewrite"]}
    assert len(pages) >= 5
    assert hinge["drop_any_one_rewrite_still_no_threshold"] is True
    assert hinge["drop_any_one_negative_still_no_threshold"] is True


def test_word_only_tfidf_also_finds_no_lock_threshold():
    result = run()
    assert result["word_only"]["threshold_any_matches_lock"] is False
    assert result["word_only"]["hinge"]["n_inverted_rewrite"] >= 5


def test_krouter_is_deterministic_on_this_map():
    a = run()
    b = run()
    assert a["systems"]["krouter"]["cases"] == b["systems"]["krouter"]["cases"]
