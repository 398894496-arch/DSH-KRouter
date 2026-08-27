#!/usr/bin/env python3
"""Reproduce the lock-vs-neighbor experiment.

Naive retrievers see every markdown file, including expired pages.
Ablations get the same metadata the lock has: `invalid_at` (`*_live`) and the
live alias table with nouns prepended (`tfidf_map`).

Scoring is exact path match. Citing a neighbor is a failure. A miss is success
when gold is null. N=22. Not LongMemEval. Not a neural encoder.
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

from canonical_lookup import in_force, live_rows, load_rows, lookup, parse_frontmatter  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_VAULT = HERE / "vault"
DEFAULT_MAP = HERE / "canonical_sources.psv"
DEFAULT_GOLD = HERE / "gold.jsonl"
TODAY = date(2026, 8, 27)
MISS = None
TOKEN = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.I)
THRESHOLDS = (0.0, 0.05, 0.08, 0.10, 0.15, 0.19, 0.20, 0.23, 0.25, 0.30)


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


def live_md_files(vault: Path, today: date) -> list[Path]:
    """Drop pages whose frontmatter is expired or not yet valid. Unmapped pages stay."""
    kept: list[Path] = []
    for path in md_files(vault):
        live, _, _ = in_force(parse_frontmatter(path), today)
        if live:
            kept.append(path)
    return kept


def map_texts(vault: Path, rows, today: date) -> list[tuple[str, str]]:
    """Live alias rows only. Aliases are prepended so cosine sees the same nouns."""
    out: list[tuple[str, str]] = []
    for _case_id, aliases, source, _anchor in live_rows(rows, vault, today):
        text = " ".join(aliases) + "\n" + read(vault / source)
        out.append((source.replace("\\", "/"), text))
    return out


def build_tfidf(files: list[Path], vault: Path):
    return build_tfidf_texts([(rel(p, vault), read(p)) for p in files])


def build_tfidf_texts(named: list[tuple[str, str]]):
    docs = [(name, features(text)) for name, text in named]
    df: Counter[str] = Counter()
    for _, bag in docs:
        df.update(bag.keys())
    n = max(len(docs), 1)
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}

    def vec(bag: Counter[str]) -> dict[str, float]:
        return {term: (1 + math.log(count)) * idf.get(term, 0.0) for term, count in bag.items()}

    doc_vecs = [(name, vec(bag)) for name, bag in docs]
    return doc_vecs, vec


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


def tfidf_predict(query: str, doc_vecs, vec, min_score: float = 0.0) -> str | None:
    qv = vec(features(query))
    ranked = sorted(
        ((cosine(qv, dv), name) for name, dv in doc_vecs),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked or ranked[0][0] < min_score:
        return MISS
    if ranked[0][0] <= 0:
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


def timed(bucket: list[float], fn):
    t0 = time.perf_counter()
    value = fn()
    bucket.append((time.perf_counter() - t0) * 1000)
    return value


def run(
    vault: Path = DEFAULT_VAULT,
    map_path: Path = DEFAULT_MAP,
    gold_path: Path = DEFAULT_GOLD,
) -> dict:
    gold = load_gold(gold_path)
    files = md_files(vault)
    live_files = live_md_files(vault, TODAY)
    rows = load_rows(map_path)
    doc_vecs, vec = build_tfidf(files, vault)
    live_vecs, live_vec = build_tfidf(live_files, vault)
    map_vecs, map_vec = build_tfidf_texts(map_texts(vault, rows, TODAY))

    systems = {
        "krouter": [],
        "lexical": [],
        "tfidf": [],
        "hybrid": [],
        "lexical_live": [],
        "tfidf_live": [],
        "tfidf_map": [],
        "hybrid_live": [],
    }
    latencies_ms: dict[str, list[float]] = {name: [] for name in systems}

    for item in gold:
        q = item["query"]
        systems["krouter"].append(
            score_one(timed(latencies_ms["krouter"], lambda: krouter_predict(q, rows, vault)), item)
        )
        systems["lexical"].append(
            score_one(timed(latencies_ms["lexical"], lambda: lexical_predict(q, files, vault)), item)
        )
        systems["tfidf"].append(
            score_one(timed(latencies_ms["tfidf"], lambda: tfidf_predict(q, doc_vecs, vec)), item)
        )
        systems["hybrid"].append(
            score_one(
                timed(
                    latencies_ms["hybrid"],
                    lambda: rrf([lexical_ranks(q, files, vault), tfidf_ranks(q, doc_vecs, vec)]),
                ),
                item,
            )
        )
        systems["lexical_live"].append(
            score_one(
                timed(latencies_ms["lexical_live"], lambda: lexical_predict(q, live_files, vault)),
                item,
            )
        )
        systems["tfidf_live"].append(
            score_one(
                timed(latencies_ms["tfidf_live"], lambda: tfidf_predict(q, live_vecs, live_vec)),
                item,
            )
        )
        systems["tfidf_map"].append(
            score_one(
                timed(latencies_ms["tfidf_map"], lambda: tfidf_predict(q, map_vecs, map_vec)),
                item,
            )
        )
        systems["hybrid_live"].append(
            score_one(
                timed(
                    latencies_ms["hybrid_live"],
                    lambda: rrf(
                        [
                            lexical_ranks(q, live_files, vault),
                            tfidf_ranks(q, live_vecs, live_vec),
                        ]
                    ),
                ),
                item,
            )
        )

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
    curve = []
    for floor in THRESHOLDS:
        scored = [
            score_one(tfidf_predict(item["query"], map_vecs, map_vec, min_score=floor), item)
            for item in gold
        ]
        block = summarize(scored)
        block.pop("rows")
        hit = block["slices"]["hit"]["exact"]
        neg_miss = block["slices"]["negative"]["miss"]
        curve.append(
            {
                "min_score": floor,
                "hit_exact": hit,
                "negative_miss": neg_miss,
                "false_neighbor": block["false_neighbor"],
                "exact": block["exact"],
                "matches_lock": hit == 1.0
                and neg_miss == 1.0
                and block["false_neighbor"] == 0,
            }
        )
    out["threshold_curve"] = curve
    out["threshold_any_matches_lock"] = any(point["matches_lock"] for point in curve)
    return out


def print_table(result: dict) -> None:
    n = result["systems"]["krouter"]["n"]
    slices = result["systems"]["krouter"]["slices"]
    counts = " ".join(f"{name}={block['n']}" for name, block in slices.items())
    print(f"today={result['today']}  N={n} ({counts})")
    print(
        f"{'system':<14} {'exact':>8} {'falseN':>8} {'oldPg':>8} {'miss':>8} {'p50ms':>8}"
    )
    for name, block in result["systems"].items():
        print(
            f"{name:<14} {block['exact']:>8.2%} {block['false_neighbor']:>8.2%} "
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
    print()
    print("tfidf_map cosine threshold sweep (same live map; miss if top-1 < min_score)")
    print(f"{'min_score':>9} {'hit':>8} {'negMiss':>8} {'falseN':>8} {'matches_lock':>14}")
    for point in result["threshold_curve"]:
        print(
            f"{point['min_score']:>9.2f} {point['hit_exact']:>8.0%} "
            f"{point['negative_miss']:>8.0%} {point['false_neighbor']:>8.0%} "
            f"{str(point['matches_lock']):>14}"
        )
    print(
        "any threshold matches lock (hit 10/10 and negative 4/4 miss and false_neighbor 0):",
        result["threshold_any_matches_lock"],
    )


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
