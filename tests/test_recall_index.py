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


def test_token_fallback_fragment_does_not_lock():
    rows = [("Q05", ["纠错优先级", "最新纠正"], "AGENTS.md", "用户当前指令和最新纠正优先")]
    assert lookup("Claude Code 纠错", rows) is None
    assert lookup("纠错优先级", rows)[0] == "Q05"


def test_rejected_source_is_not_locked(tmp_path):
    from canonical_lookup import lookup as lk

    v = tmp_path / "v"
    write(v, "old.md", "---\nstatus: rejected\n---\n")
    write(v, "new.md", "---\nstatus: active\n---\n")
    rows = [("Q18", ["项目阶段诊断"], "old.md", "x"), ("Q19", ["真实任务"], "new.md", "y")]
    assert lk("项目阶段诊断", rows, vault=v) is None
    assert lk("真实任务", rows, vault=v)[0] == "Q19"


def test_single_keyword_query_is_answered(vault):
    res = r.recall(vault, "封账")
    assert res["confidence"] != "none"
    assert hits(res)[0] == "02 经验与方法/搜索与知识库/封账先看时间日志文件.md"


def test_bare_number_is_not_a_content_term(vault):
    res = r.recall(vault, "2026")
    assert res["confidence"] == "none"


def test_route_widens_from_single_file_scope(vault, monkeypatch, tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1] / "skill/krouter-obsidian/scripts/route_knowledge.py"
    write(vault, "02 经验与方法/Agent/用户偏好与工作约束.md", "---\ntitle: 用户偏好\n---\n\n名称要能看懂。\n")
    env = {**__import__("os").environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_STATE_DIR": str(tmp_path / "state")}
    out = subprocess.run([sys.executable, str(root), "preference", "封账 时间日志"], capture_output=True, text=True, env=env).stdout
    assert "scope_widened: vault" in out
    assert "封账先看时间日志文件.md" in out
    log = (tmp_path / "state" / "queries.jsonl").read_text(encoding="utf-8")
    assert "ranked-recall-complete+widened" in log


def test_reconsolidate_reads_only_weak_queries(tmp_path):
    import json

    import reconsolidate as rc

    log = tmp_path / "q.jsonl"
    log.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
        {"ts": "2026-10-01T00:00:00Z", "q": "没答好", "status": "bounded-literal-search-complete"},
        {"ts": "2026-10-01T00:00:01Z", "q": "低置信", "status": "ranked-recall-complete", "confidence": "low"},
        {"ts": "2026-10-01T00:00:02Z", "q": "答好了", "status": "ranked-recall-complete", "confidence": "high"},
        {"ts": "2026-09-01T00:00:00Z", "q": "游标之前", "status": "bounded-literal-search-complete"},
    ]), encoding="utf-8")
    got = [row["q"] for row in rc.load_misses(log, "2026-09-30T00:00:00Z")]
    assert got == ["没答好", "低置信"]


def test_checkup_flags_dead_lock_and_tenure(vault, tmp_path):
    import subprocess
    import sys

    write(vault, "02 经验与方法/准经验/新排版规则.md",
          "---\ntitle: 新排版规则\nstatus: active\nsupersedes:\n  - \"[[02 经验与方法/准经验/旧排版规则]]\"\n---\n\n排版形态和动画要多变。\n")
    psv = tmp_path / "m2.psv"
    psv.write_text("Q09|旧规则|02 经验与方法/准经验/旧排版规则.md|x\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "skill/krouter-obsidian/scripts/checkup.py"
    env = {**__import__("os").environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_STATE_DIR": str(tmp_path / "s")}
    subprocess.run([sys.executable, str(script), "--map", str(psv), "--days", "1"], check=True, env=env, capture_output=True)
    page = (vault / "90 系统文件/自动化/下意识体检.md").read_text(encoding="utf-8")
    assert "Q09 →" in page and "superseded" in page
    assert "tenure: \"1/1\"" in page


def test_function_bigram_does_not_carry_a_refusal(vault):
    assert r.recall(vault, "帮我写一首关于秋天的诗")["confidence"] == "none"


def test_unknown_latin_term_is_refused(vault):
    assert r.recall(vault, "Kubernetes的排版怎么扩容")["confidence"] == "none"


def test_topic_page_needs_to_be_named(vault):
    write(vault, "02 经验与方法/主题档案/主题｜Grok 订阅.md",
          "---\ntitle: 主题｜Grok 订阅\ntopic_terms: grok-fixed;Grok订阅\n---\n\n排版 排版 排版 时间日志 封账 时间日志 封账。\n")
    unnamed = r.recall(vault, "封账要看时间日志吗", limit=5)
    assert unnamed["hits"][0]["rel"] != "02 经验与方法/主题档案/主题｜Grok 订阅.md"
    named = r.recall(vault, "grok-fixed 封账", limit=5)
    assert named["hits"][0]["rel"] == "02 经验与方法/主题档案/主题｜Grok 订阅.md"
    assert named["hits"][0]["tier"] == "topic"


def test_consolidate_topics_writes_cited_provisional_page(vault, monkeypatch):
    import consolidate_topics as ct

    write(vault, "05 时间日志/2026-10/02｜修补丁.md", "---\ntitle: 02｜修补丁\n---\n\n中文补丁又掉了，用户要求重装。\n")
    write(vault, ct.LIST, "cn|中文补丁|中文补丁|\n")
    seen = {}

    def fake(cli, model, prompt):
        seen["prompt"] = prompt
        return ("## 一句话\n补丁反复掉。[[05 时间日志/2026-10/02｜修补丁]]\n## 当前状态\n截至 2026-10-02 未修好。[[不存在的页]]\n"
                "## 关键事实\n- x\n## 用户纠错与踩过的坑\n- y\n## 时间线\n- z\n## 未决与不确定\n- w\n## 相关页面\n- v\nTRIGGERS: 中文又丢了;汉化补丁")

    monkeypatch.setattr(ct, "call_model", fake)
    res = ct.build(vault, ct.load_list(vault)[0], "cli", "m", False)
    assert res["status"] == "written" and res["bad_links"] == 1 and not res["missing_sections"]
    page = (vault / ct.OUT_DIR / "主题｜中文补丁.md").read_text(encoding="utf-8")
    assert "status: provisional" in page and "topic_terms: 中文补丁" in page
    assert "triggers: 中文补丁;中文又丢了;汉化补丁" in page
    assert "`不存在的页`（未找到此页）" in page and "[[05 时间日志/2026-10/02｜修补丁]]" in page
    assert "05 时间日志/2026-10/02｜修补丁.md" in seen["prompt"]
    assert ct.build(vault, ct.load_list(vault)[0], "cli", "m", False)["status"] == "unchanged"
