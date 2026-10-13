"""Answer or refuse: a small logistic regression over the signals recall already computes.

The hand-written refusal rules in recall_index (score floor, matched words, unknown words, unknown characters, words
the vault lacks) each looked at one signal and were tuned one threshold at a time; every round of that fitted the
questions it was tuned on. This combines them, plus signals BM25 does not have, into one calibrated probability that
the top page answers the question:

- lexical: the top score against the vault-size floor, the gap to the second page, matched content words, missing
  words, unknown words and characters, the old rule's own verdict;
- the host's own words: how many question words the page's triggers carry (aliases, learned triggers, checked cards);
- sentence evidence: how much of the question the best single line of the page covers (a neighbour page looks right
  as a whole but has no line that covers the question's distinctive words);
- dense (only when local embeddings are on): the page's similarity, whether it is in the embedding top 5, whether
  both retrievers put it first.

Weights are trained offline on development questions only (bench/memory_honesty/train_decider.py) and stored in
`decider_weights.json` next to this file. No weights file, or a feature set it does not cover: recall keeps its
rules. Deterministic at query time; no dependency beyond the standard library.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

WEIGHTS = Path(__file__).resolve().parent / "decider_weights.json"
_CACHE: dict = {}

# 只用和库无关的量：比值、比例、排名、是否。绝对分数（bm25 的量级、向量相似度）一换库就变了刻度
LEX = ("ratio", "idf_cover", "cover", "trig_share", "rule_refuse")
DENSE = ("d_rank", "d_agree")


def load() -> dict:
    if "w" not in _CACHE:
        try:
            _CACHE["w"] = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE["w"] = {}
    return _CACHE["w"]


def model(dense_on: bool) -> dict | None:
    """The weight set for this situation: `lexical` or `dense`, or None (recall keeps its rules)."""
    w = load()
    return w.get("dense" if dense_on else "lexical") or None


def probability(feats: dict[str, float], m: dict) -> float:
    z = m["bias"]
    for name, coef in m["coef"].items():
        mu, sd = m["mean"][name], m["std"][name] or 1.0
        z += coef * (feats.get(name, 0.0) - mu) / sd
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def line_cover(lines: list[str], qtok: list[str], tokens) -> float:
    """Share of the question's content tokens that the best single line of the page contains."""
    if not qtok or not lines:
        return 0.0
    want = set(qtok)
    return max(len(want & set(tokens(ln))) for ln in lines) / len(want)


def features(*, margin: float, idf_cover: float, cover: float, triggers: int, qterms: int, rule_refuse: bool,
             dense: dict | None = None) -> dict[str, float]:
    f = {
        "ratio": math.log(max(1.0, min(margin, 9.9))),
        "idf_cover": idf_cover,
        "cover": cover,
        "trig_share": min(1.0, triggers / max(qterms, 1)),
        "rule_refuse": float(rule_refuse),
    }
    if dense is not None:
        f["d_rank"] = 1.0 / dense["rank"] if dense.get("rank") else 0.0
        f["d_agree"] = float(dense.get("agree", 0.0))
    return f


def train(xs: list[dict[str, float]], ys: list[int], ws: list[float], names: tuple[str, ...], l2: float = 1.0,
          steps: int = 4000, lr: float = 0.1) -> dict:
    """Weighted, L2-regularised logistic regression by gradient descent on standardised features. Pure Python;
    a few hundred examples train in well under a second."""
    n = len(xs)
    mean = {k: sum(x.get(k, 0.0) for x in xs) / n for k in names}
    std = {k: (sum((x.get(k, 0.0) - mean[k]) ** 2 for x in xs) / n) ** 0.5 for k in names}
    zs = [[(x.get(k, 0.0) - mean[k]) / (std[k] or 1.0) for k in names] for x in xs]
    coef = [0.0] * len(names)
    bias = 0.0
    wsum = sum(ws)
    for _ in range(steps):
        gb, gc = 0.0, [0.0] * len(names)
        for z, y, w in zip(zs, ys, ws):
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, bias + sum(c * v for c, v in zip(coef, z))))))
            e = (p - y) * w
            gb += e
            for i, v in enumerate(z):
                gc[i] += e * v
        bias -= lr * gb / wsum
        coef = [c - lr * (g / wsum + l2 * c / wsum) for c, g in zip(coef, gc)]
    return {"bias": bias, "coef": dict(zip(names, coef)), "mean": mean, "std": std}
