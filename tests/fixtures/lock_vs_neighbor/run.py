#!/usr/bin/env python3
"""Reproduce the lock-vs-neighbor experiment.

Four retrievers on the same fixture vault and gold file:

- krouter: alias table, miss is allowed, expired map rows dropped
- lexical: python count of query tokens in each markdown file, miss if none
- tfidf: word + char-ngram TF-IDF cosine, always returns top-1
- hybrid: Reciprocal Rank Fusion of lexical and tfidf, always returns top-1
  if either ranked a file

This is not LongMemEval. Scoring is exact path match. Citing a neighbor is
a miss against gold, not a partial credit. The CI vector is TF-IDF cosine,
not a neural encoder; install sentence-transformers and pass --encoder
sbert only if you want that extra row.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skill/krouter-obsidian/scripts"))

from canonical_lookup import load_rows, lookup  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_VAULT = HERE / "vault"
DEFAULT_MAP = HERE / "canonical_sources.psv"
DEFAULT_GOLD = HERE / "gold.jsonl"
TODAY = date(2026, 8, 27)
MISS = None
TOKEN = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.I)


def rel(path: Path, vault: Path) -> str:
    return path.relative_to(vault).as_posix()


def md_files(vault: Path) -> list[Path]:
    return sorted(
        p
        for p in vault.rglob("*.md")
        if p.is_file() and ".obsidian" not in p.parts
    )


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN.finditer(text)]


def char_ngrams(text: str, n: int = 3) -> list[str]:
    compact = re.sub(r"\s+", " ", text.lower())
    if len(compact) < n:
        return [compact] if compact else []
    return [compact[i : i + n] for i in range(len(compact) - n + 1)]


def features(text: str) -> Counter[str]:
    bag: Counter[str] = Counter()
    bag.update(f"w:{t}" for t in tokens(text))
    bag.update(f"c:{g}" for g in char_ngrams(text, 3))
    return bag


def load_gold(path: Path) -> list[dict]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def krouter_predict(query: str, rows, vault: Path) -> str | None:
    hit = lookup(query, rows, vault=vault, today=TODAY)
    if hit is None:
        return MISS
    return hit[1].replace("\\", "/")


def lexical_predict(query: str, files: list[Path], vault: Path) -> str | None:
    qtok = tokens(query)
    if not qtok:
        return MISS
    scored: list[tuple[int, str]] = []
    for path in files:
        text = read(path).lower()
        score = sum(text.count(tok) for tok in qtok)
        if score:
            scored.append((score, rel(path, vault)))
    if not scored:
        return MISS
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def build_tfidf(files: list[Path], vault: Path):
    docs = [(rel(p, vault), features(read(p))) for p in files]
    df: Counter[str] = Counter()
    for _, bag in docs:
        df.update(bag.keys())
    n = len(docs)
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}

    def vec(bag: Counter[str]) -> dict[str, float]:
        return {term: (1 + math.log(count)) * idf.get(term, 0.0) for term, count in bag.items()}

    doc_vecs = [(name, vec(bag)) for name, bag in docs]
    return doc_vecs, idf, vec


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    num = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)


def tfidf_predict(query: str, doc_vecs, vec) -> str | None:
    qv = vec(features(query))
    ranked = sorted(
        ((cosine(qv, dv), name) for name, dv in doc_vecs),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked or ranked[0][0] <= 0:
        return MISS
    return ranked[0][1]


def tfidf_ranks(query: str, doc_vecs, vec) -> list[str]:
    qv = vec(features(query))
    ranked = sorted(
        ((cosine(qv, dv), name) for name, dv in doc_vecs),
        key=lambda item: (-item[0], item[1]),
    )
    return [name for score, name in ranked if score > 0]


def lexical_ranks(query: str, files: list[Path], vault: Path) -> list[str]:
    qtok = tokens(query)
    scored: list[tuple[int, str]] = []
    for path in files:
        text = read(path).lower()
        score = sum(text.count(tok) for tok in qtok) if qtok else 0
        if score:
            scored.append((score, rel(path, vault)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored]


def rrf(rank_lists: list[list[str]], k: int = 60) -> str | None:
    scores: dict[str, float] = defaultdict(float)
    for ranks in rank_lists:
        for i, name in enumerate(ranks):
            scores[name] += 1.0 / (k + i + 1)
    if not scores:
        return MISS
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def score_one(pred: str | None, item: dict) -> dict:
    gold = item.get("gold")
    old = item.get("old")
    trap = item.get("trap")
    exact = pred == gold
    false_neighbor = pred is not None and pred != gold
    old_page = bool(old) and pred == old
    trapped = bool(trap) and pred == trap
    return {
        "id": item["id"],
        "slice": item["slice"],
        "query": item["query"],
        "gold": gold,
        "pred": pred,
        "exact": exact,
        "false_neighbor": false_neighbor,
        "old_page": old_page,
        "trapped": trapped,
        "miss": pred is None,
    }


def summarize(rows: list[dict]) -> dict:
    def rate(pred, subset=None):
        use = [r for r in rows if subset is None or r["slice"] == subset]
        if not use:
            return None
        return round(sum(1 for r in use if pred(r)) / len(use), 4)

    slices = {}
    for name in ("hit", "supersede", "neighbor", "negative"):
        part = [r for r in rows if r["slice"] == name]
        if not part:
            continue
        slices[name] = {
            "n": len(part),
            "exact": rate(lambda r: r["exact"], name),
            "false_neighbor": rate(lambda r: r["false_neighbor"], name),
            "old_page": rate(lambda r: r["old_page"], name),
            "trapped": rate(lambda r: r["trapped"], name),
            "miss": rate(lambda r: r["miss"], name),
        }
    return {
        "n": len(rows),
        "exact": rate(lambda r: r["exact"]),
        "false_neighbor": rate(lambda r: r["false_neighbor"]),
        "old_page": rate(lambda r: r["old_page"]),
        "miss": rate(lambda r: r["miss"]),
        "slices": slices,
        "rows": rows,
    }


def run(
    vault: Path = DEFAULT_VAULT,
    map_path: Path = DEFAULT_MAP,
    gold_path: Path = DEFAULT_GOLD,
) -> dict:
    gold = load_gold(gold_path)
    files = md_files(vault)
    rows = load_rows(map_path)
    doc_vecs, _idf, vec = build_tfidf(files, vault)

    systems = {
        "krouter": [],
        "lexical": [],
        "tfidf": [],
        "hybrid": [],
    }
    latencies_ms: dict[str, list[float]] = {name: [] for name in systems}

    for item in gold:
        q = item["query"]

        t0 = time.perf_counter()
        k = krouter_predict(q, rows, vault)
        latencies_ms["krouter"].append((time.perf_counter() - t0) * 1000)
        systems["krouter"].append(score_one(k, item))

        t0 = time.perf_counter()
        lex = lexical_predict(q, files, vault)
        latencies_ms["lexical"].append((time.perf_counter() - t0) * 1000)
        systems["lexical"].append(score_one(lex, item))

        t0 = time.perf_counter()
        tf = tfidf_predict(q, doc_vecs, vec)
        latencies_ms["tfidf"].append((time.perf_counter() - t0) * 1000)
        systems["tfidf"].append(score_one(tf, item))

        t0 = time.perf_counter()
        hy = rrf(
            [
                lexical_ranks(q, files, vault),
                tfidf_ranks(q, doc_vecs, vec),
            ]
        )
        latencies_ms["hybrid"].append((time.perf_counter() - t0) * 1000)
        systems["hybrid"].append(score_one(hy, item))

    out = {
        "today": TODAY.isoformat(),
        "vault": str(vault),
        "map": str(map_path),
        "gold": str(gold_path),
        "systems": {},
    }
    for name, scored in systems.items():
        summary = summarize(scored)
        times = sorted(latencies_ms[name])
        summary["latency_p50_ms"] = round(times[len(times) // 2], 3)
        summary.pop("rows")
        summary["cases"] = scored
        out["systems"][name] = summary
    return out


def print_table(result: dict) -> None:
    print(f"today={result['today']}  n={result['systems']['krouter']['n']}")
    print(
        f"{'system':<10} {'exact':>8} {'falseN':>8} {'oldPg':>8} {'miss':>8} {'p50ms':>8}"
    )
    for name, block in result["systems"].items():
        print(
            f"{name:<10} {block['exact']:>8.2%} {block['false_neighbor']:>8.2%} "
            f"{block['old_page']:>8.2%} {block['miss']:>8.2%} {block['latency_p50_ms']:>8.3f}"
        )
    print()
    print("by slice (exact / false_neighbor / old_page)")
    for slice_name in ("hit", "supersede", "neighbor", "negative"):
        parts = []
        for name, block in result["systems"].items():
            sl = block["slices"][slice_name]
            parts.append(
                f"{name} {sl['exact']:.0%}/{sl['false_neighbor']:.0%}/{sl['old_page']:.0%}"
            )
        print(f"  {slice_name:<10} " + "  ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_table(result)
        first = run()
        second = run()
        same = first["systems"]["krouter"]["cases"] == second["systems"]["krouter"]["cases"]
        print()
        print("krouter determinism (two runs, same preds):", same)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
