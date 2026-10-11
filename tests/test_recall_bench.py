"""Public recall benchmark on the shipped template: refuse instead of guess holds at the recall layer too.

`tests/fixtures/recall_bench.jsonl`: questions with a gold page, questions the vault cannot answer,
and half-off-topic questions that borrow one vault word (`咖啡机的定时器多久除垢一次`). Anyone can rerun
it from a clone; CI fails if refusals slip or the gold page stops coming first.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import recall_index as ri

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "tests/fixtures/recall_bench.jsonl"
POS_TOP1_MIN = 9  # English gold-page questions, of 12; raise it when recall gets better, never lower it to make a change pass
POS_ZH_TOP1_MIN = 9  # the same 12 asked in Chinese (0.9.3: 9, 0.10.1: 5 — a small vault refused common characters)


def test_recall_bench(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    shutil.copytree(REPO / "template", vault)
    monkeypatch.setenv("KROUTER_CACHE_DIR", str(tmp_path / "cache"))
    rows = [json.loads(x) for x in BENCH.read_text(encoding="utf-8").splitlines() if x.strip()]
    pos_ok, pos_zh_ok, wrong_answers = 0, 0, []
    for it in rows:
        res = ri.recall(vault, it["q"], limit=3)
        top = res["hits"][0]["rel"] if res["hits"] and res["confidence"] != "none" else None
        if it["expect"] and it["kind"] == "pos_zh":
            pos_zh_ok += top == it["expect"]
        elif it["expect"]:
            pos_ok += top == it["expect"]
        elif res["confidence"] != "none":
            wrong_answers.append((it["kind"], it["q"], top, res["confidence"]))
    assert not wrong_answers, wrong_answers  # off-topic and half-off-topic: every one refused
    assert pos_ok >= POS_TOP1_MIN, pos_ok
    assert pos_zh_ok >= POS_ZH_TOP1_MIN, pos_zh_ok
