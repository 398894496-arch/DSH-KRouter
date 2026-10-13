#!/usr/bin/env python3
"""Prototype: dense retrieval on the memory honesty bench, alone and combined with KRouter. Not part of the product.

Embeddings run locally (fastembed, ONNX; the model is downloaded once), so questions never leave the machine. Model:
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (English and Chinese). Pages are embedded as title +
body without frontmatter; vectors are cached under `KROUTER_CACHE_DIR` (or a temp dir) by model and page hash.

Variants, each with superseded pages handled like KRouter does:
- `dense`:  cosine top hit, superseded pages left out, refuse below a floor picked on the dev set (`run.pick_floor`).
- `rescue`: KRouter first; when KRouter refuses, answer with its own best page if the dense top hit is that same page
            and the dense score clears a floor picked on the dev set. KRouter's off-vault checks still apply first.
- `gate`:   dense ranking, KRouter's refusal decision (refuse when KRouter refuses), superseded links followed.

    python3 bench/memory_honesty/dense.py --set dev3
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location("mh_bench_dense", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
MODEL = os.environ.get("KROUTER_DENSE_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
_EMB = None


def embedder():
    global _EMB
    if _EMB is None:
        from fastembed import TextEmbedding

        _EMB = TextEmbedding(MODEL)
    return _EMB


def embed(texts: list[str], kind: str = "query") -> list[list[float]]:
    import numpy as np

    if "e5" in MODEL.lower():  # e5 models are trained with these prefixes; without them they score lower
        texts = [("query: " if kind == "query" else "passage: ") + t for t in texts]
    vecs = list(embedder().embed(texts))
    return [list(v / (np.linalg.norm(v) or 1.0)) for v in vecs]


def page_text(path: Path) -> tuple[str, dict]:
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---\n"):
        head, _, body = raw[4:].partition("\n---")
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return (meta.get("title") or path.stem) + "\n" + body.strip("-\n "), meta


VAULT = bench.HERE / "vault"  # set by main() from the question set: vault/ or vault2/


def pages() -> list[tuple[str, str, dict]]:
    root = VAULT
    out = []
    for path in sorted(root.rglob("*.md")):
        text, meta = page_text(path)
        out.append((path.relative_to(root).as_posix(), text, meta))
    return out


def page_vectors() -> dict[str, list[float]]:
    cache = Path(os.environ.get("KROUTER_CACHE_DIR") or tempfile.gettempdir()) / "krouter-dense"
    cache.mkdir(parents=True, exist_ok=True)
    ps = pages()
    key = hashlib.sha1((MODEL + "".join(r + t for r, t, _ in ps)).encode("utf-8")).hexdigest()[:16]
    f = cache / f"{key}.json"
    if f.is_file():
        return json.loads(f.read_text())
    vecs = embed([t for _, t, _ in ps], kind="passage")
    data = {r: [float(x) for x in v] for (r, _, _), v in zip(ps, vecs)}
    f.write_text(json.dumps(data))
    return data


def superseded() -> set[str]:
    return {r for r, _, m in pages() if m.get("status", "").lower() == "superseded"}


def dense_scored(rows: list[dict], skip: bool = True) -> list[tuple[str, list[tuple[str, float]]]]:
    import numpy as np

    pv = page_vectors()
    dead = superseded() if skip else set()
    rels = [r for r in pv if r not in dead]
    mat = np.array([pv[r] for r in rels])
    qv = np.array(embed([it["q"] for it in rows]))
    out = []
    for it, v in zip(rows, qv):
        sims = mat @ v
        order = np.argsort(-sims)[:3]
        out.append((it["id"], [(rels[i], float(sims[i])) for i in order]))
    return out


def dev_name() -> str:
    return "dev3" if VAULT.name == "vault2" else "dev"


def dense_answers(rows: list[dict]) -> list[dict]:
    dev = bench.questions(dev_name())
    floor = bench.pick_floor(dev, dense_scored(dev))
    return bench.floor_answers(dense_scored(rows), floor)


def _krouter_raw(rows: list[dict]) -> list[dict]:
    """KRouter's recall with its decision and its best page even when it refuses."""
    sys.path.insert(0, str(REPO / "skill/krouter-obsidian/scripts"))
    os.environ["KROUTER_NO_QUERY_LOG"] = "1"
    with tempfile.TemporaryDirectory(prefix="krouter-dense-", ignore_cleanup_errors=True) as tmp:
        os.environ["KROUTER_CACHE_DIR"] = str(Path(tmp) / "cache")
        vault = Path(tmp) / "vault"
        shutil.copytree(VAULT, vault)
        import recall_index as ri

        out = []
        for it in rows:
            res = ri.recall(vault, it["q"], limit=3)
            out.append({"id": it["id"], "refused": res["confidence"] == "none" or not res["hits"],
                        "top": res["hits"][0]["rel"] if res["hits"] else None,
                        "cited": [h["rel"] for h in res["hits"]]})
        return out


def rescue_answers(rows: list[dict], floor: float | None = None) -> list[dict]:
    if floor is None:
        dev = bench.questions(dev_name())
        kd, dd = _krouter_raw(dev), dict(dense_scored(dev))
        cands = sorted({h[0][1] for h in dd.values() if h})
        best, floor = None, 1.0
        for f in cands:
            res = bench.score(dev, _rescue(kd, dd, f))
            util = int(res["correction_hit"].split("/")[0]) + int(res["current_hit"].split("/")[0]) - res["wrong_citations"]
            if best is None or util > best:
                best, floor = util, f
    return _rescue(_krouter_raw(rows), dict(dense_scored(rows)), floor)


def _rescue(kr: list[dict], dd: dict, floor: float) -> list[dict]:
    out = []
    for a in kr:
        if not a["refused"]:
            out.append({"id": a["id"], "refused": False, "cited": a["cited"]})
            continue
        hits = dd.get(a["id"]) or []
        ok = bool(hits) and hits[0][1] >= floor and a["top"] is not None and hits[0][0] == a["top"]
        out.append({"id": a["id"], "refused": not ok, "cited": [hits[0][0]] if ok else []})
    return out


def agree_answers(rows: list[dict], lex_floor: float | None = None, dense_floor: float | None = None) -> list[dict]:
    """Two independent retrievers must agree: lexical (BM25 over character pairs and words, superseded pages left
    out) and dense. A neighbour question tends to look like one page to one of them and another page to the other;
    a real question about a page tends to land on it in both. Answer only when their top pages agree and each clears
    a floor picked on the dev set (one sweep over both floors, same utility as `run.pick_floor`)."""
    if lex_floor is None or dense_floor is None:
        dev = bench.questions(dev_name())
        lx, dn = dict(lex_scored(dev)), dict(dense_scored(dev))
        lcands = sorted({0.0} | {h[0][1] for h in lx.values() if h})
        dcands = sorted({-1.0} | {h[0][1] for h in dn.values() if h})
        best = None
        for lf in lcands[:: max(1, len(lcands) // 25)]:
            for df in dcands[:: max(1, len(dcands) // 25)]:
                res = bench.score(dev, _agree(dev, lx, dn, lf, df))
                util = int(res["correction_hit"].split("/")[0]) + int(res["current_hit"].split("/")[0]) - res["wrong_citations"]
                if best is None or util > best[0]:
                    best = (util, lf, df)
        _, lex_floor, dense_floor = best
    return _agree(rows, dict(lex_scored(rows)), dict(dense_scored(rows)), lex_floor, dense_floor)


def lex_scored(rows: list[dict]):
    return bench.bm25_scored(rows, vault_src=VAULT, cjk=True)


def _agree(rows, lx, dn, lf, df):
    out = []
    for it in rows:
        a, b = lx.get(it["id"]) or [], dn.get(it["id"]) or []
        ok = bool(a and b) and a[0][0] == b[0][0] and a[0][1] >= lf and b[0][1] >= df
        out.append({"id": it["id"], "refused": not ok, "cited": [a[0][0]] if ok else []})
    return out


def vote_answers(rows: list[dict]) -> list[dict]:
    """`agree`, plus KRouter's own answers that the dense retriever confirms (same top page). Two pairs of independent
    signals; an answer needs one pair to agree. Floors for the lexical/dense pair come from `agree` (picked on dev)."""
    base = {a["id"]: a for a in agree_answers(rows)}
    dn = dict(dense_scored(rows))
    out = []
    for k in _krouter_raw(rows):
        a = base[k["id"]]
        hits = dn.get(k["id"]) or []
        if a["refused"] and not k["refused"] and hits and k["top"] == hits[0][0]:
            a = {"id": k["id"], "refused": False, "cited": k["cited"]}
        out.append(a)
    return out


def gate_answers(rows: list[dict]) -> list[dict]:
    kr = {a["id"]: a for a in _krouter_raw(rows)}
    out = []
    for qid, hits in dense_scored(rows):
        refused = kr[qid]["refused"] or not hits
        out.append({"id": qid, "refused": refused, "cited": [] if refused else [h[0] for h in hits]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--variant", choices=["dense", "rescue", "gate", "agree", "vote", "all"], default="all")
    args = ap.parse_args()
    global VAULT
    VAULT = bench.vault_of(args.set)
    rows = bench.questions(args.set)
    variants = ["dense", "rescue", "gate", "agree", "vote"] if args.variant == "all" else [args.variant]
    for v in variants:
        ans = {"dense": dense_answers, "rescue": rescue_answers, "gate": gate_answers, "agree": agree_answers, "vote": vote_answers}[v](rows)
        res = bench.score(rows, ans)
        if args.set in bench.HELDOUT_SETS:
            res = bench.aggregate(res)
        right = int(res["correction_hit"].split("/")[0]) + int(res["current_hit"].split("/")[0])
        print(json.dumps({"variant": v, "wrong": f"{res['wrong_citations']}/{res['answered']}", "refused": res["refused"],
                          "right": right, "corr": res["correction_hit"], "cur": res["current_hit"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
