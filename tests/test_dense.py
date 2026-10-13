"""Optional local embeddings (dense.py): off by default, answers only when the lexical and dense rankings agree, never
breaks a route. The real model is not available in CI; `KROUTER_DENSE_FAKE=1` swaps in a deterministic stand-in."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skill/krouter-obsidian/scripts"
sys.path.insert(0, str(SCRIPTS))

import dense  # noqa: E402
import recall_index as ri  # noqa: E402


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    shutil.copytree(REPO / "bench/memory_honesty/vault", v)
    monkeypatch.setenv("KROUTER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("KROUTER_DENSE_CONFIG", str(tmp_path / "dense.json"))
    monkeypatch.setenv("KROUTER_DENSE_FAKE", "1")
    monkeypatch.delenv("KROUTER_DENSE", raising=False)
    dense._EMB = None
    return v


def _on(tmp_path: Path, model: str = dense.DEFAULT_MODEL) -> None:
    (tmp_path / "dense.json").write_text(json.dumps({"enabled": True, "model": model}), encoding="utf-8")


def test_off_by_default_changes_nothing(vault):
    res = ri.recall(vault, "How do we ship a release?", limit=3)
    assert res["dense"] == "off" and res["confidence"] != "none"


def test_building_falls_back_to_lexical(vault, tmp_path):
    _on(tmp_path)
    res = ri.recall(vault, "How do we ship a release?", limit=3)  # 30 页都还没有向量：超过查询时顺手补算的上限
    assert res["dense"] == "building" and res["confidence"] != "none"


def test_agreement_answers_and_disagreement_refuses(vault, tmp_path, monkeypatch):
    _on(tmp_path)
    con = ri.connect(ri.cache_path(vault))
    ri.refresh(vault, con)
    assert dense.build(vault, con, dense.DEFAULT_MODEL) == 30
    monkeypatch.setitem(dense.FLOORS, dense.DEFAULT_MODEL, 0.0)
    good = ri.recall(vault, "How do we ship a release?", limit=3)
    assert good["dense"] == "agree" and good["hits"][0]["rel"] == "Engineering/Release process.md"
    assert good["hits"][0]["dense"] > 0
    # 让向量那一票永远投给别的页：两边不一致 → 拒答
    real = dense.top_pages
    monkeypatch.setattr(dense, "top_pages", lambda *a, **k: {"state": "on", "floor": 0.0,
                                                              "hits": [("Engineering/Date format.md", 0.99)]})
    bad = ri.recall(vault, "How do we ship a release?", limit=3)
    assert bad["dense"] == "disagree" and bad["confidence"] == "none"
    monkeypatch.setattr(dense, "top_pages", real)
    monkeypatch.setitem(dense.FLOORS, dense.DEFAULT_MODEL, 1.01)  # 下限高于任何相似度：不作答
    assert ri.recall(vault, "How do we ship a release?", limit=3)["confidence"] == "none"


def test_vectors_follow_page_edits(vault, tmp_path):
    _on(tmp_path)
    con = ri.connect(ri.cache_path(vault))
    ri.refresh(vault, con)
    dense.build(vault, con, dense.DEFAULT_MODEL)
    assert dense.build(vault, con, dense.DEFAULT_MODEL) == 0  # 没改过的页不重算
    page = vault / "Engineering/Date format.md"
    page.write_text(page.read_text(encoding="utf-8") + "\nAlso store the time zone name.\n", encoding="utf-8")
    (vault / "Engineering/Translations.md").unlink()
    assert dense.build(vault, con, dense.DEFAULT_MODEL) == 1
    rels = {r for (r,) in con.execute("SELECT DISTINCT rel FROM dense")}
    assert "Engineering/Translations.md" not in rels and len(rels) == 29
    st = dense.status(vault, con, dense.DEFAULT_MODEL)
    assert st["coverage"] == 1.0 and st["floor_calibrated"] is True


def test_a_broken_model_never_breaks_a_route(vault, tmp_path, monkeypatch):
    _on(tmp_path)
    con = ri.connect(ri.cache_path(vault))
    ri.refresh(vault, con)
    dense.build(vault, con, dense.DEFAULT_MODEL)
    monkeypatch.setattr(dense, "embed", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model file missing")))
    res = ri.recall(vault, "How do we ship a release?", limit=3)
    assert res["dense"] == "error" and res["confidence"] != "none"  # 退回纯字面，不报错


def test_receipt_says_dense_state_and_kill_switch(vault, tmp_path):
    _on(tmp_path)
    env = {**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_NO_QUERY_LOG": "1"}
    out = subprocess.run([sys.executable, str(SCRIPTS / "route_knowledge.py"), "search", "How do we ship a release?"],
                         env=env, capture_output=True, text=True, timeout=120).stdout
    assert "dense: building" in out  # 回执说明这次为什么没用上向量
    off = subprocess.run([sys.executable, str(SCRIPTS / "route_knowledge.py"), "search", "How do we ship a release?"],
                         env={**env, "KROUTER_DENSE": "0"}, capture_output=True, text=True, timeout=120).stdout
    assert "dense:" not in off


def test_reexec_only_when_on_and_the_venv_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("KROUTER_DENSE_CONFIG", str(tmp_path / "none.json"))
    calls = []
    monkeypatch.setattr(os, "execv", lambda *a: calls.append(a))
    dense.reexec_if_needed("x.py", [])
    assert not calls  # 没开：不切换
    _on(tmp_path)
    monkeypatch.setenv("KROUTER_DENSE_CONFIG", str(tmp_path / "dense.json"))
    monkeypatch.setenv("KROUTER_DENSE_HOME", str(tmp_path / "no-venv"))
    dense.reexec_if_needed("x.py", [])
    assert not calls  # 开了但 venv 还没装：照旧在当前解释器里跑（退回纯字面）


def test_chunks_carry_the_title_and_cap_long_pages():
    body = "\n\n".join(f"Paragraph {i} " + "word " * 120 for i in range(30))
    parts = dense.chunks("Release process", body)
    assert len(parts) == dense.MAX_CHUNKS and all(p.startswith("Release process\n") for p in parts)


def test_strict_tier_needs_the_same_first_page(vault, tmp_path, monkeypatch):
    _on(tmp_path)
    con = ri.connect(ri.cache_path(vault))
    ri.refresh(vault, con)
    dense.build(vault, con, dense.DEFAULT_MODEL)
    monkeypatch.setitem(dense.FLOORS, dense.DEFAULT_MODEL, 0.0)
    # 向量把正确页排第二：平衡档前 5 名有交集仍可作答，严格档要首选相同 → 拒答
    monkeypatch.setattr(dense, "top_pages", lambda *a, **k: {"state": "on", "floor": 0.0, "hits": [
        ("Engineering/Date format.md", 0.9), ("Engineering/Release process.md", 0.8)]})
    q = "Can I cut a release from my feature branch to ship it?"
    monkeypatch.setenv("KROUTER_DENSE_TIER", "strict")
    assert ri.recall(vault, q, limit=3)["confidence"] == "none"
    assert dense.tier() == "strict"
    monkeypatch.delenv("KROUTER_DENSE_TIER")
    assert dense.tier() == "balanced"
