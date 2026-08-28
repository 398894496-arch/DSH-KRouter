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


def test_dense_ablation_closes_the_supersede_gap():
    """Same invalid_at filter. MiniLM still needed the metadata for 3/4 expired pages."""
    result = run()
    naive = result["systems"]["dense"]["slices"]["supersede"]
    assert naive["old_page"] >= 0.75
    for name in ("dense_live", "dense_map"):
        sl = result["systems"][name]["slices"]["supersede"]
        assert sl["old_page"] == 0, name
        assert sl["exact"] == 1.0, name


def test_unthresholded_dense_map_does_not_refuse():
    result = run()
    mapped = result["systems"]["dense_map"]
    assert mapped["slices"]["negative"]["n"] == N_NEGATIVE
    assert mapped["slices"]["negative"]["miss"] == 0


def test_dense_raises_cjk_rewrites_above_ood_negatives():
    """The lexical inversion is gone. MiniLM is not TF-IDF."""
    result = run()
    hinge = result["dense_hinge"]
    assert hinge["n_rewrite"] == N_REWRITE
    assert hinge["n_inverted_rewrite"] == 0
    assert hinge["min_rewrite"] > hinge["max_negative"]


def test_no_dense_map_threshold_matches_the_lock_on_this_fixture():
    """MiniLM: precision. H15 发版 is already the wrong live page before any floor."""
    result = run()
    assert result["dense_model"] == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert result["dense_threshold_curve"]
    assert result["dense_threshold_any_matches_lock"] is False
    zero = result["dense_threshold_curve"][0]
    assert zero["min_score"] == 0.0
    assert zero["negative_miss"] == 0
    assert zero["hit_exact"] < 1.0
    assert "H15" in zero["missed_hits"]
    h15 = next(c for c in result["systems"]["dense_map"]["cases"] if c["id"] == "H15")
    assert h15["query"] == "发版"
    assert h15["gold"] == "02 经验与方法/Deploy/Ship from main only.md"
    assert h15["pred"] == "02 经验与方法/Automation/Seal the day from the log file.md"
    assert h15["false_neighbor"] is True
    assert result["dense_hinge"]["n_inverted_rewrite"] == 0
    assert result["dense_hinge"]["drop_any_one_rewrite_still_no_threshold"] is True
    assert result["dense_hinge"]["drop_any_one_negative_still_no_threshold"] is True


def test_middleweight_bge_m3_hits_every_alias_and_still_cannot_refuse():
    """Unthresholded BGE-M3: 16/16 hits, still cites every OOD negative."""
    result = run()
    mapped = result["systems"]["dense_m3_map"]
    assert result["dense_m3_model"] == "BAAI/bge-m3"
    assert mapped["slices"]["hit"]["exact"] == 1.0
    assert mapped["slices"]["negative"]["miss"] == 0
    assert mapped["slices"]["supersede"]["exact"] == 1.0
    naive = result["systems"]["dense_m3"]["slices"]["supersede"]
    assert naive["old_page"] == 1.0
    hinge = result["dense_m3_hinge"]
    assert hinge["n_inverted_rewrite"] == 0
    assert hinge["min_rewrite"] > hinge["max_negative"]
    assert result["dense_m3_threshold_any_matches_lock"] is False
    zero = result["dense_m3_threshold_curve"][0]
    assert zero["negative_miss"] == 0
    h15 = next(c for c in mapped["cases"] if c["id"] == "H15")
    assert h15["exact"] is True


def test_bge_m3_floor_040_leftover_is_neighbor_b03():
    """Near-miss: 16/16 hits and 12/12 OOD refuse; leftover is neighbor B03, not a 13th negative."""
    result = run()
    gold_b03 = next(item for item in GOLD if item["id"] == "B03")
    assert gold_b03["slice"] == "neighbor"
    assert gold_b03["gold"] is None
    point = next(p for p in result["dense_m3_threshold_curve"] if p["min_score"] == 0.40)
    assert point["hit_exact"] == 1.0
    assert point["negative_miss"] == 1.0
    assert point["leftover_false_neighbor"] == ["B03"]
    assert point["missed_hits"] == []
    assert point["matches_lock"] is False
    later = next(p for p in result["dense_m3_threshold_curve"] if p["min_score"] == 0.45)
    assert later["false_neighbor"] == 0
    assert later["leftover_false_neighbor"] == []
    assert later["negative_miss"] == 1.0
    assert later["hit_exact"] < 1.0
    assert later["missed_hits"]


def test_krouter_is_deterministic_on_this_map():
    a = run()
    b = run()
    assert a["systems"]["krouter"]["cases"] == b["systems"]["krouter"]["cases"]
