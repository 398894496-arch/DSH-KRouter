from pathlib import Path

import pytest

from canonical_lookup import lookup, near_score, suggestions

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "skill/krouter-obsidian/scripts/canonical_sources.psv"
VAULT = ROOT / "template"


@pytest.fixture(scope="module")
def rows():
    from canonical_lookup import load_rows

    return load_rows(MAP)


def test_exact_home(rows):
    hit = lookup("home", rows)
    assert hit is not None
    assert hit[0] == "Q01"
    assert hit[1] == "Agent第二大脑.md"


def test_clippings(rows):
    hit = lookup("clippings", rows)
    assert hit is not None
    assert hit[0] == "Q02"


def test_preference_alias(rows):
    hit = lookup("preference", rows)
    assert hit is not None
    assert hit[0] == "Q02"


def test_memory_alias(rows):
    hit = lookup("memory", rows)
    assert hit is not None
    assert hit[0] == "Q07"


def test_ambiguous_different_files_is_miss(tmp_path):
    from canonical_lookup import load_rows, lookup

    path = tmp_path / "map.psv"
    path.write_text("Q1|alpha|a.md|x\nQ2|alpha|b.md|y\n", encoding="utf-8")
    rows = load_rows(path)
    assert lookup("alpha", rows) is None


def test_same_file_tie_picks_lowest_id(tmp_path):
    from canonical_lookup import load_rows, lookup

    path = tmp_path / "map.psv"
    path.write_text("Q2|alpha|a.md|x\nQ1|alpha|a.md|y\n", encoding="utf-8")
    rows = load_rows(path)
    hit = lookup("alpha", rows)
    assert hit is not None
    assert hit[0] == "Q1"


def test_prefix_is_suggestion_not_hit(rows):
    assert lookup("homz", rows) is None
    ranked = suggestions("homz", rows, limit=3)
    ids = [item[1] for item in ranked]
    assert "Q01" in ids
    assert near_score("homz", "home") >= 40


def test_latin_fragment_of_an_alias_is_not_a_hit(rows):
    """`how` sits inside `how to handle clippings`. That is not a hit."""
    assert lookup("how", rows) is None
    assert lookup("how to deploy", rows) is None
    assert lookup("how do I add my own topic", rows) is None
    ranked = suggestions("how to deploy", rows, limit=3)
    assert ranked, "a miss still owes the caller hints"


def test_short_alias_inside_a_question_still_hits(rows):
    assert lookup("correction policy for my team", rows)[0] == "Q05"
    assert lookup("homepage", rows)[0] == "Q01"


def test_cjk_fragment_still_carries_the_alias(tmp_path):
    from canonical_lookup import load_rows, lookup

    path = tmp_path / "map.psv"
    path.write_text("Q1|唯一总入口|a.md|x\n", encoding="utf-8")
    rows = load_rows(path)
    assert lookup("入口", rows)[0] == "Q1"


def test_template_sources_exist(rows):
    for _case_id, _aliases, source, _anchor in rows:
        assert (VAULT / source).is_file(), source
