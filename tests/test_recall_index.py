from pathlib import Path

import pytest

import recall_index as r
from canonical_lookup import alias_score, lookup


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("KROUTER_CACHE_DIR", str(tmp_path / "cache"))
    psv = tmp_path / "map.psv"
    psv.write_text("# id|aliases|source|anchor\nQ01|主入口;总入口|Agent第二大脑.md|唯一总入口\n", encoding="utf-8")
    monkeypatch.setenv("KROUTER_MAP", str(psv))
    v = tmp_path / "vault"
    write(v, "Agent第二大脑.md", "---\ntitle: Agent第二大脑\nstatus: active\n---\n\n整个知识库只从这里进入。\n")
    write(
        v,
        "02 经验与方法/短视频/包装排版准纠错.md",
        "---\ntitle: 包装排版准纠错\nstatus: provisional\n---\n\n"
        "1. **排版形态和动画要多变，内容要丰富。** 每一页换一种版式。\n",
    )
    write(
        v,
        "02 经验与方法/准经验/旧排版规则.md",
        "---\ntitle: 旧排版规则\nstatus: superseded\n---\n\n排版形态统一用左侧标题，动画固定。\n",
    )
    write(
        v,
        "02 经验与方法/搜索与知识库/封账先看时间日志文件.md",
        "---\ntitle: 封账先看时间日志文件\nstatus: active\n---\n\n时间日志文件存在且不是待总结，这一天就已封账。\n",
    )
    write(v, "05 时间日志/2026-10/01｜日常.md", "---\ntitle: 01｜日常\n---\n\n今天整理了排版，也看了时间日志。\n")
    write(v, "Clippings/剪藏.md", "排版 封账 时间日志 全都在这里\n")
    return v


def hits(res):
    return [h["rel"] for h in res["hits"]] if res["confidence"] != "none" else []


def test_tokens_split_cjk_bigrams_and_latin():
    assert r.tokens("日更健康 Groq whisper") == ["日更", "更健", "健康", "groq", "whisper"]


def test_rule_page_ranks_first(vault):
    res = r.recall(vault, "封账要看时间日志吗")
    assert hits(res)[0] == "02 经验与方法/搜索与知识库/封账先看时间日志文件.md"
    assert res["hits"][0]["tier"] == "rule"


def test_clippings_are_not_indexed(vault):
    res = r.recall(vault, "封账 时间日志 排版", limit=10)
    assert all(not h["rel"].startswith("Clippings/") for h in res["hits"])


def test_superseded_page_ranks_below_live_one(vault):
    rels = [h["rel"] for h in r.recall(vault, "排版形态 动画", limit=5)["hits"]]
    assert rels.index("02 经验与方法/短视频/包装排版准纠错.md") < rels.index("02 经验与方法/准经验/旧排版规则.md")


def test_unknown_question_is_refused(vault):
    res = r.recall(vault, "比特币现在多少钱")
    assert res["confidence"] == "none"


def test_sidecar_triggers_bridge_paraphrase(vault):
    before = r.recall(vault, "画面太单调被骂了")
    assert "02 经验与方法/短视频/包装排版准纠错.md" not in hits(before)
    write(vault, "90 系统文件/Claude Code协作/下意识触发词.psv",
          "02 经验与方法/短视频/包装排版准纠错.md|画面太单调;版式单调;动画不够多变\n")
    after = r.recall(vault, "画面太单调被骂了")
    assert hits(after)[0] == "02 经验与方法/短视频/包装排版准纠错.md"


def test_scope_restricts_hits(vault):
    res = r.recall(vault, "封账 时间日志", scope="05 时间日志", limit=5)
    assert res["hits"] and all(h["rel"].startswith("05 时间日志/") for h in res["hits"])


def test_incremental_refresh_picks_up_edits(vault):
    con = r.connect(r.cache_path(vault))
    assert r.refresh(vault, con)["added"] == 5
    assert r.refresh(vault, con) == {"added": 0, "changed": 0, "removed": 0, "docs": 5}
    write(vault, "Agent第二大脑.md", "---\ntitle: Agent第二大脑\n---\n\n入口改了。\n")
    assert r.refresh(vault, con)["changed"] == 1


def test_how_skips_status_line_and_prefers_bold_rule():
    body = "provisional（准纠错）\n\n背景说明一段文字在这里。\n\n1. **英文证据一律截翻译后的页面。** 原话略。\n"
    assert r.first_rule_line(body).startswith("英文证据一律截翻译后的页面")


def test_short_alias_inside_long_question_does_not_lock():
    assert alias_score("日更能不能交给云端自动化跑", "日更") < 100
    assert alias_score("日更", "日更") >= 1000
    assert alias_score("每日进化运行状态怎么看", "每日进化运行状态") >= 500


def test_lookup_refuses_short_alias_lock():
    rows = [("Q21", ["日更", "日更健康"], "90 系统文件/自动化/日更健康.md", "当前健康以本页为准")]
    assert lookup("日更能不能交给云端自动化跑", rows) is None
    assert lookup("日更健康", rows)[0] == "Q21"
