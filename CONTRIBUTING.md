# Contributing

This repo stays a deterministic router. Do not add a vector index, embedding daemon, or retrieval subprocess as the default path. The lock-vs-neighbor MiniLM and BGE-M3 rows are frozen cosine replays (`dense_vectors.json`, `dense_m3_vectors.json`), not a product retriever.

1. `python3 -m pip install -r requirements.txt -r requirements-dev.txt`
2. `python3 -m pytest -q`
3. `./scripts/first_run.sh`

Before **upload** (`git push` / a release): commit, then `./scripts/verify_clean.sh`. That script unpacks `git archive HEAD` into a temp dir — uncommitted and untracked files are not there. A green pytest in a dirty worktree is not this check. v0.4.1 shipped `verify_canonical_map.py` against helpers that only existed uncommitted.

A miss may print alias **suggestions**. Those are hints to add or retry a noun. They are not `canonical_match: true`.
