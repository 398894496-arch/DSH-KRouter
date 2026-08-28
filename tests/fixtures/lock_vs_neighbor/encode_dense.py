#!/usr/bin/env python3
"""Encode the lock-vs-neighbor fixture.

Default pytest does not import this file. CI replays the JSON.
Recompute after gold or vault text changes:

    HF_HUB_DISABLE_XET=1 python3 tests/fixtures/lock_vs_neighbor/encode_dense.py
    HF_HUB_DISABLE_XET=1 python3 tests/fixtures/lock_vs_neighbor/encode_dense.py --mid
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import (  # noqa: E402
    DEFAULT_DENSE,
    DEFAULT_DENSE_MID,
    DEFAULT_GOLD,
    DEFAULT_MAP,
    DEFAULT_VAULT,
    DENSE_MID_MODEL,
    DENSE_MID_SEQ,
    DENSE_MODEL,
    DENSE_SEQ,
    TODAY,
    dense_fingerprint,
    load_gold,
    load_rows,
    live_md_files,
    map_texts,
    md_files,
    read,
    rel,
)


def encode_minilm(load_id: str, max_seq: int):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(load_id)
    model.max_seq_length = max_seq

    def encode_named(pairs: list[tuple[str, str]]) -> dict[str, list[float]]:
        vectors = model.encode(
            [text for _, text in pairs],
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return {
            name: [round(float(x), 6) for x in vec]
            for (name, _), vec in zip(pairs, vectors)
        }

    return encode_named


def encode_bge_m3(load_id: str, max_seq: int):
    import torch
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(load_id, local_files_only=True)
    mdl = AutoModel.from_pretrained(load_id, local_files_only=True)
    mdl.eval()

    def encode_named(pairs: list[tuple[str, str]]) -> dict[str, list[float]]:
        names = [name for name, _ in pairs]
        texts = [text for _, text in pairs]
        vecs: list[list[float]] = []
        batch_size = 4
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            batch = tok(
                chunk,
                padding=True,
                truncation=True,
                max_length=max_seq,
                return_tensors="pt",
            )
            with torch.no_grad():
                hidden = mdl(**batch).last_hidden_state[:, 0]
                hidden = F.normalize(hidden, p=2, dim=1)
            vecs.extend(hidden.cpu().tolist())
            print(f"bge-m3 encoded {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
        return {
            name: [round(float(x), 6) for x in vec]
            for name, vec in zip(names, vecs)
        }

    return encode_named


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mid", action="store_true", help="encode BGE-M3 (middleweight)")
    parser.add_argument("--from-dir", help="load model from a local snapshot instead of Hub")
    args = parser.parse_args()

    max_seq = DENSE_MID_SEQ if args.mid else DENSE_SEQ
    out = DEFAULT_DENSE_MID if args.mid else DEFAULT_DENSE
    load_id = args.from_dir or (DENSE_MID_MODEL if args.mid else DENSE_MODEL)
    stored_model = DENSE_MID_MODEL if args.mid else DENSE_MODEL

    gold = load_gold(DEFAULT_GOLD)
    vault = DEFAULT_VAULT
    files = md_files(vault)
    live_files = live_md_files(vault, TODAY)
    named_map = map_texts(vault, load_rows(DEFAULT_MAP), TODAY)
    fingerprint = dense_fingerprint(gold, files, live_files, named_map, vault)

    queries = [(item["id"], item["query"]) for item in gold]
    docs_all = [(rel(p, vault), read(p)) for p in files]
    docs_live = [(rel(p, vault), read(p)) for p in live_files]
    docs_map = list(named_map)

    encode_named = (
        encode_bge_m3(load_id, max_seq) if args.mid else encode_minilm(load_id, max_seq)
    )

    payload = {
        "model": stored_model,
        "max_seq_length": max_seq,
        "normalize": True,
        "pooling": "cls" if args.mid else "sentence-transformers",
        "recorded_at": "2026-08-28",
        "fingerprint": fingerprint,
        "queries": encode_named(queries),
        "docs_all": encode_named(docs_all),
        "docs_live": encode_named(docs_live),
        "docs_map": encode_named(docs_map),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}  queries={len(payload['queries'])}  model={stored_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
