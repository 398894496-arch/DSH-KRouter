#!/usr/bin/env python3
"""Train decider.py's answer-or-refuse model on development questions only. Never on vault3 / any held-out set.

Training data: dev and dev2 (vault/), dev3 (vault2/), and optionally a private file of real-vault questions
(`--real FILE --real-vault DIR`, JSONL with `q` and `expect`, the page or null; weight `--real-weight`, default 3).
Each question runs through KRouter's recall with feature collection on; the label is 1 when its candidate page is the
gold page, 0 otherwise (a neighbour question, or the wrong page).

Reports leave-one-set-out results (train on the other sets, pick the threshold there, score the left-out set), then
trains on everything and writes `skill/krouter-obsidian/scripts/decider_weights.json` with `--write`.

    python3 bench/memory_honesty/train_decider.py --real ~/eval.jsonl --real-vault ~/Vault [--dense] [--write]

`--dense` trains the weight set used when local embeddings are on (needs dense.py's model; vectors are built first).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPTS = REPO / "skill/krouter-obsidian/scripts"
spec = importlib.util.spec_from_file_location("mh_bench_train", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
sys.path.insert(0, str(SCRIPTS))
os.environ["KROUTER_NO_QUERY_LOG"] = "1"
import decider  # noqa: E402
import recall_index as ri  # noqa: E402


def collect(rows: list[dict], vault_src: Path, dense_on: bool, cache: Path | None = None, copy: bool = True) -> list[dict]:
    """[{x, y, kind, gold, cand}] — features and label per question, with the decider switched off."""
    decider._CACHE["w"] = {}
    ri.COLLECT_FEATURES = True
    tmp = Path(tempfile.mkdtemp(prefix="krouter-train-"))
    os.environ["KROUTER_CACHE_DIR"] = str(cache or tmp / "cache")
    vault = vault_src
    if copy:
        vault = tmp / "vault"
        shutil.copytree(vault_src, vault)
    if dense_on:
        import dense

        con = ri.connect(ri.cache_path(vault))
        ri.refresh(vault, con)
        dense.build(vault, con, dense.config()["model"])
    out = []
    for it in rows:
        res = ri.recall(vault, it["q"], limit=3)
        gold = it.get("gold", it.get("expect"))
        kind = "refuse" if gold is None else (it["kind"] if it.get("kind") in ("correction", "current") else "current")
        it = {**it, "kind": kind}
        f = res.get("features")
        if f is None:  # 字面一条都没命中：只能拒答，不进训练
            out.append({"x": None, "y": 0, "kind": kind, "gold": gold, "cand": None})
            continue
        out.append({"x": f, "y": int(gold is not None and res["candidate"] == gold),
                    "kind": kind, "gold": gold,
                    "cand": res["candidate"]})
    ri.COLLECT_FEATURES = False
    return out


def evaluate(exs: list[dict], m: dict, threshold: float) -> dict:
    """right / wrong / answered / neighbours refused at this threshold."""
    right = wrong = answered = ref = neigh = 0
    for e in exs:
        if e["kind"] == "refuse":
            neigh += 1
        ok = e["x"] is not None and decider.probability(e["x"], m) >= threshold
        if not ok:
            ref += e["kind"] == "refuse"
            continue
        answered += 1
        if e["gold"] is not None and e["cand"] == e["gold"]:
            right += 1
        else:
            wrong += 1
    return {"right": right, "wrong": wrong, "answered": answered, "refused": f"{ref}/{neigh}"}


def pick_threshold(exs: list[dict], m: dict, weights: list[float]) -> float:
    best, best_t = None, 0.5
    for t in [i / 100 for i in range(5, 96)]:
        u = 0.0
        for e, w in zip(exs, weights):
            if e["x"] is None or decider.probability(e["x"], m) < t:
                continue
            u += w * (1 if e["gold"] is not None and e["cand"] == e["gold"] else -1)
        if best is None or u > best:
            best, best_t = u, t
    return best_t


def fit(sets: dict[str, list[dict]], wts: dict[str, float], names, l2: float) -> dict:
    exs = [e for s, es in sets.items() for e in es if e["x"] is not None]
    ws = [wts[s] for s, es in sets.items() for e in es if e["x"] is not None]
    m = decider.train([e["x"] for e in exs], [e["y"] for e in exs], ws, names, l2=l2)
    allx = [e for s, es in sets.items() for e in es]
    allw = [wts[s] for s, es in sets.items() for e in es]
    m["threshold"] = pick_threshold(allx, m, allw)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default="")
    ap.add_argument("--real-vault", default="")
    ap.add_argument("--real-cache", default="", help="a recall cache for the real vault with vectors already built")
    ap.add_argument("--real-weight", type=float, default=3.0)
    ap.add_argument("--dense", action="store_true")
    ap.add_argument("--l2", type=float, default=2.0)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if not args.dense:
        os.environ["KROUTER_DENSE"] = "0"
    names = decider.LEX + (decider.DENSE if args.dense else ())
    sets = {"dev": collect(bench.questions("dev"), bench.vault_of("dev"), args.dense),
            "dev2": collect(bench.questions("dev2"), bench.vault_of("dev2"), args.dense),
            "dev3": collect(bench.questions("dev3"), bench.vault_of("dev3"), args.dense)}
    wts = {"dev": 1.0, "dev2": 1.0, "dev3": 1.0}
    if args.real:
        rows = [json.loads(x) for x in Path(args.real).read_text(encoding="utf-8").splitlines() if x.strip()]
        sets["real"] = collect(rows, Path(args.real_vault), args.dense,
                               cache=Path(args.real_cache) if args.real_cache else None, copy=False)
        wts["real"] = args.real_weight
    print(json.dumps({"examples": {s: len(e) for s, e in sets.items()}, "dense": args.dense}))
    # 同一套评估口径下的手写规则：rule_refuse = 0 就作答，候选页同上（向量开着时就是方案 B 的规则判断）
    rules = {"bias": 0.0, "coef": {"rule_refuse": -10.0}, "mean": {"rule_refuse": 0.0}, "std": {"rule_refuse": 1.0}}
    print(json.dumps({"hand_rules": {s: evaluate(e, rules, 0.5) for s, e in sets.items()}}))
    # 按库留一：dev 和 dev2 是同一个库（vault1），一起留出；不然模型已经见过这个库，结果偏乐观
    vaults = {"vault1": ["dev", "dev2"], "vault2": ["dev3"], "real": ["real"]}
    for name, left in vaults.items():
        if not all(s in sets for s in left):
            continue
        m = fit({s: e for s, e in sets.items() if s not in left}, wts, names, args.l2)
        print(json.dumps({"left_out_vault": name, "threshold": m["threshold"],
                          **{s: evaluate(sets[s], m, m["threshold"]) for s in left}}))
    m = fit(sets, wts, names, args.l2)
    print(json.dumps({"all": {s: evaluate(e, m, m["threshold"]) for s, e in sets.items()}, "threshold": m["threshold"],
                      "coef": {k: round(v, 3) for k, v in m["coef"].items()}}, ensure_ascii=False))
    if args.write:
        path = SCRIPTS / "decider_weights.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data["dense" if args.dense else "lexical"] = {**m, "trained_on": sorted(sets), "l2": args.l2,
                                                       "real_weight": wts.get("real")}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"wrote": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
