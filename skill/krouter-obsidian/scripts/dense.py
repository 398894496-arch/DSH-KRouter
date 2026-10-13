#!/usr/bin/env python3
"""Optional local embeddings for recall: a second, independent opinion on which page a question is about.

Off unless the host turned it on (`bootstrap.py --dense`, or `dense.py --enable`). When on, recall answers only when
the lexical ranking and the embedding model put the same page first; a neighbour question that fools one rarely fools
both (docs/BENCHMARK.md, vault2). The lock is untouched: an alias-table hit still decides alone.

Everything runs on this machine. The model (default `jinaai/jina-embeddings-v2-base-zh`, about 640 MB, English and
Chinese) is downloaded once into `~/.cache/krouter/models`; fastembed lives in its own virtualenv,
`~/.local/share/krouter/dense`, so the router itself still needs nothing but the standard library. Page vectors live in
the recall cache next to the full-text index, keyed by the page's body hash, so only changed pages are re-embedded.

Never fails a route: missing package, missing model, an index still being built — recall falls back to lexical only and
says so (`dense: off|building|error`).

    python3 dense.py --enable              # make the venv, install fastembed, download the model (asks nothing; the
                                           # installer asks first)
    python3 dense.py --build --vault V     # embed every page (install and the nightly job run this)
    python3 dense.py --status --vault V
    python3 dense.py --disable
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "jinaai/jina-embeddings-v2-base-zh"
# 两边首选一致、且向量相似度过这个下限才作答。按模型给固定值，不依赖某个库自己的开发集：jina 的 0.5 是在
# 评审写的 vault2 dev3 上按「答对 − 引错」最大选的（0.5 与 0.55 打平，按规则取低的；0.45 时引错跳到 6 道）。
# 别的模型还没标定，先用同一个值，并在 status 里说明
FLOORS = {"jinaai/jina-embeddings-v2-base-zh": 0.5}
FLOOR_UNCALIBRATED = 0.5
CHUNK = 600          # 每段最多多少字
MAX_CHUNKS = 4       # 每页最多几段（长页只看开头这些；8 段时作者库 1206 个文件首次建要 29 分钟，4 段 17 分钟）
# 按页面类型给段数：规则页、主题页是问题最常落到的地方；项目资料、日志、会话摘录量大，只看开头一段
CARD_VECTORS = False  # 核对过的问答卡问题也作为这一页的向量。作者库实测没有提升、多花约 3 分钟，默认关
TIER_CHUNKS = {"rule": 4, "topic": 4, "other": 2, "project": 1, "log": 1, "dead": 1}
BUILD_ON_QUERY = 20  # 查询时最多顺手补算几页；更多就留给夜间任务，这次退回纯字面
COVERAGE_MIN = 0.95  # 已有向量的页面少于这个比例：视为还在建，退回纯字面

_EMB = None


def home_dir() -> Path:
    return Path(os.environ.get("KROUTER_DENSE_HOME") or Path.home() / ".local/share/krouter/dense")


def model_dir() -> Path:
    if os.environ.get("KROUTER_MODEL_DIR"):
        return Path(os.environ["KROUTER_MODEL_DIR"])
    return Path.home() / ".cache/krouter/models"


def config_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(os.environ.get("KROUTER_DENSE_CONFIG") or Path(base) / "krouter" / "dense.json")


def config() -> dict:
    if os.environ.get("KROUTER_DENSE") == "0":
        return {}
    try:
        cfg = json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not cfg.get("enabled"):
        return {}
    cfg.setdefault("model", DEFAULT_MODEL)
    return cfg


def venv_python() -> Path:
    return home_dir() / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def reexec_if_needed(script: str, argv: list[str]) -> None:
    """The router runs on the system python3; fastembed lives in the dense venv. When dense is on and this
    interpreter cannot import fastembed, run the same script again under the venv's python (once)."""
    if not config() or os.environ.get("KROUTER_DENSE_REEXEC") == "1":
        return
    try:
        import fastembed  # noqa: F401

        return
    except ImportError:
        pass
    py = venv_python()
    # venv 里的 python 是指向系统解释器的链接，解析后两者相同；看 sys.prefix 才知道是不是已经在 venv 里
    if py.is_file() and Path(sys.prefix).resolve() != home_dir().resolve():
        os.environ["KROUTER_DENSE_REEXEC"] = "1"
        os.execv(str(py), [str(py), script, *argv])


def embedder(model: str):
    global _EMB
    if _EMB is None or _EMB[0] != model:
        if os.environ.get("KROUTER_DENSE_FAKE") == "1":  # tests: a deterministic stand-in, no download
            _EMB = (model, _Fake())
        else:
            from fastembed import TextEmbedding

            model_dir().mkdir(parents=True, exist_ok=True)
            _EMB = (model, TextEmbedding(model, cache_dir=str(model_dir())))
    return _EMB[1]


class _Fake:
    """Hashed bag of words and character pairs; similar wording → similar vector. Only for tests."""

    def embed(self, texts):
        for t in texts:
            v = [0.0] * 256
            toks = re.findall(r"[a-z0-9]+", t.lower())
            for run in re.findall(r"[㐀-鿿]+", t):
                toks += [run[i:i + 2] for i in range(max(1, len(run) - 1))]
            for tok in toks:
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 256] += 1.0
            yield v


def _norm(v) -> list[float]:
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [float(x) / n for x in v]


def embed(texts: list[str], model: str, kind: str) -> list[list[float]]:
    if "e5" in model.lower():
        texts = [("query: " if kind == "query" else "passage: ") + t for t in texts]
    return [_norm(v) for v in embedder(model).embed(texts)]


def chunks(title: str, body: str, cap: int = MAX_CHUNKS) -> list[str]:
    """Title + body cut at paragraph boundaries into pieces of at most CHUNK characters; every piece starts with the
    title, so a piece about one detail still knows which page it is on."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK:
            out.append(cur)
            cur = ""
        cur = (cur + "\n" + p).strip() if cur else p[: CHUNK * 2]
    if cur:
        out.append(cur)
    return [f"{title}\n{c}" for c in (out or [""])[:cap]]


def ensure_table(con: sqlite3.Connection) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS dense(rel TEXT, sha TEXT, model TEXT, n INTEGER, vec BLOB)")
    con.execute("CREATE INDEX IF NOT EXISTS dense_rel ON dense(rel, model)")


def _pack(v: list[float]) -> bytes:
    return array.array("f", v).tobytes()


def _unpack(b: bytes) -> list[float]:
    a = array.array("f")
    a.frombytes(b)
    return list(a)


def pending(vault: Path, con: sqlite3.Connection, model: str) -> list[tuple[str, str, str, str, int]]:
    """Pages whose vectors are missing or stale: [(rel, sha, title, body, chunk budget)]."""
    import recall_index as ri
    from krouter_redact import redact

    ensure_table(con)
    have = {(r, s) for r, s in con.execute("SELECT DISTINCT rel, sha FROM dense WHERE model = ?", (model,))}
    cards = card_questions(vault) if CARD_VECTORS else {}
    out = []
    for full, rel in ri.walk_md(vault):
        try:
            raw = Path(full).read_bytes()
        except OSError:
            continue
        qs = cards.get(rel, [])
        sha = ri.body_hash(raw) + ("+" + hashlib.sha1("\n".join(qs).encode("utf-8")).hexdigest()[:8] if qs else "")
        if (rel, sha) in have:
            continue
        meta, body = ri.split_frontmatter(redact(raw.decode("utf-8", errors="replace")))
        tier = ri.tier_of(ri.zones.canon(vault, rel), (meta.get("status") or "").lower())
        out.append((rel, sha, meta.get("title") or Path(rel).stem, body, TIER_CHUNKS.get(tier, 2), qs))
    return out


def card_questions(vault: Path) -> dict[str, list[str]]:
    """{page: [question of a card that still matches the page and passed its checks]} — the nightly job's guesses at how
    people ask about each page, embedded next to the page's own text."""
    import recall_index as ri

    out: dict[str, list[str]] = {}
    for rel, cs in ri.card_triggers(vault).items():
        path = vault / ri.zones.real(vault, rel)
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        hashes = ri.card_hashes(raw)
        text = raw.decode("utf-8", errors="replace")
        qs = [c["q"] for c in cs if c.get("sha") in hashes and c.get("v") and ri.grounded(c, text)]
        if qs:
            out[rel] = qs[:8]
    return out


def build(vault: Path, con: sqlite3.Connection, model: str, limit: int = 0) -> int:
    """Embed missing or changed pages (all of them when limit is 0). Returns how many pages were embedded."""
    todo = pending(vault, con, model)
    if limit:
        todo = todo[:limit]
    for rel, sha, title, body, cap, qs in todo:
        pieces = chunks(title, body, cap) + [f"{title}\n{q}" for q in qs]
        vecs = embed(pieces, model, "passage")
        con.execute("DELETE FROM dense WHERE rel = ? AND model = ?", (rel, model))
        con.executemany("INSERT INTO dense VALUES(?,?,?,?,?)", [(rel, sha, model, i, _pack(v)) for i, v in enumerate(vecs)])
    live = {rel for _f, rel in __import__("recall_index").walk_md(vault)}
    for (rel,) in con.execute("SELECT DISTINCT rel FROM dense WHERE model = ?", (model,)).fetchall():
        if rel not in live:
            con.execute("DELETE FROM dense WHERE rel = ? AND model = ?", (rel, model))
    con.commit()
    return len(todo)


def status(vault: Path, con: sqlite3.Connection, model: str) -> dict:
    import recall_index as ri

    ensure_table(con)
    total = sum(1 for _ in ri.walk_md(vault))
    stale = len(pending(vault, con, model))
    return {"model": model, "pages": total, "embedded": total - stale,
            "coverage": round((total - stale) / total, 3) if total else 1.0, "floor": FLOORS.get(model, FLOOR_UNCALIBRATED),
            "floor_calibrated": model in FLOORS}


_MATRIX: dict = {}


def _matrix(con: sqlite3.Connection, model: str):
    """(rels, float32 matrix) of every stored chunk vector, cached for the process (the MCP server keeps it);
    rebuilt when the stored set changes. None without numpy."""
    try:
        import numpy as np
    except ImportError:
        return [], None
    db = con.execute("PRAGMA database_list").fetchone()[2] or str(id(con))
    key = (db, model)  # 按缓存文件缓存：每次查询都会重新 connect，按连接对象缓存等于没缓存
    sig = con.execute("SELECT count(*), coalesce(sum(length(sha)), 0), coalesce(max(rowid), 0) FROM dense WHERE model = ?",
                      (model,)).fetchone()
    if key in _MATRIX and _MATRIX[key][0] == sig:
        return _MATRIX[key][1], _MATRIX[key][2]
    rels, rows = [], []
    for rel, blob in con.execute("SELECT rel, vec FROM dense WHERE model = ?", (model,)):
        rels.append(rel)
        rows.append(np.frombuffer(blob, dtype=np.float32))
    mat = np.vstack(rows) if rows else np.zeros((0, 1), dtype=np.float32)
    _MATRIX[key] = (sig, rels, mat)
    return rels, mat


def top_pages(vault: Path, con: sqlite3.Connection, query: str, scope: str = "", limit: int = 5) -> dict:
    """{"state": "on"|"off"|"building"|"error", "hits": [(rel, sim)]} — the dense opinion, or why there is none."""
    cfg = config()
    if not cfg:
        return {"state": "off", "hits": []}
    model = cfg["model"]
    try:
        ensure_table(con)
        # 全文索引上次变动的时间（refresh 有改动才会更新）没变，向量就不用再逐页核对；
        # 否则每次查询都要把整个库读一遍算哈希（527 页约 0.1 秒）
        built = (con.execute("SELECT v FROM meta WHERE k='built_at'").fetchone() or [""])[0]
        checked = (con.execute("SELECT v FROM meta WHERE k=?", ("dense_checked:" + model,)).fetchone() or [None])[0]
        if checked != built:
            todo = pending(vault, con, model)
            total = sum(1 for _ in __import__("recall_index").walk_md(vault)) or 1
            if todo and len(todo) <= BUILD_ON_QUERY:
                build(vault, con, model)
                todo = []
            if todo and 1 - len(todo) / total < COVERAGE_MIN:
                return {"state": "building", "hits": [], "pending": len(todo)}
            if not todo:
                con.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", ("dense_checked:" + model, built))
                con.commit()
        q = embed([query], model, "query")[0]
        rels, mat = _matrix(con, model)
        best: dict[str, float] = {}
        if mat is not None:  # numpy：一次矩阵乘法；4000 段时约几毫秒（纯 Python 逐段要约 0.5 秒）
            import numpy as np

            sims = mat @ np.asarray(q, dtype=np.float32)
            for rel, sim in zip(rels, sims.tolist()):
                if sim > best.get(rel, -2.0):
                    best[rel] = sim
        else:
            for rel, blob in con.execute("SELECT rel, vec FROM dense WHERE model = ?", (model,)):
                v = _unpack(blob)
                sim = sum(a * b for a, b in zip(q, v))
                if sim > best.get(rel, -2.0):
                    best[rel] = sim
        if scope:
            best = {r: s for r, s in best.items() if r == scope or r.startswith(scope.rstrip("/") + "/")}
        hits = sorted(best.items(), key=lambda x: -x[1])[:limit]
        return {"state": "on", "hits": hits, "floor": FLOORS.get(model, FLOOR_UNCALIBRATED)}
    except Exception as exc:  # noqa: BLE001  向量层出任何问题都退回纯字面，不让路由失败
        return {"state": "error", "hits": [], "error": str(exc)[:160]}


def enable(model: str) -> dict:
    """Make the venv, install fastembed, download the model, record the choice. Returns a summary."""
    home = home_dir()
    if not venv_python().is_file():
        subprocess.run([sys.executable, "-m", "venv", str(home)], check=True)
    subprocess.run([str(venv_python()), "-m", "pip", "install", "--quiet", "fastembed>=0.7,<1"], check=True)
    t0 = time.time()
    subprocess.run([str(venv_python()), "-c",
                    "import sys; from fastembed import TextEmbedding; TextEmbedding(sys.argv[1], cache_dir=sys.argv[2])",
                    model, str(model_dir())], check=True)
    cfg_path = config_file()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"enabled": True, "model": model}, indent=1) + "\n", encoding="utf-8")
    return {"dense": "enabled", "model": model, "python": str(venv_python()), "download_s": round(time.time() - t0)}


def main() -> int:
    ap = argparse.ArgumentParser(description="KRouter optional local embeddings")
    ap.add_argument("--vault", default="")
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--disable", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    if args.disable:
        p = config_file()
        if p.is_file():
            p.write_text(json.dumps({"enabled": False}) + "\n", encoding="utf-8")
        print(json.dumps({"dense": "disabled"}))
        return 0
    if args.enable:
        print(json.dumps(enable(args.model), ensure_ascii=False))
        return 0
    reexec_if_needed(__file__, sys.argv[1:])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import recall_index as ri
    from krouter_home import vault_path

    vault = Path(args.vault or vault_path())
    cfg = config()
    if not cfg:
        print(json.dumps({"dense": "off"}))
        return 0
    con = ri.connect(ri.cache_path(vault))
    if args.build:
        t0 = time.time()
        n = build(vault, con, cfg["model"])
        print(json.dumps({"dense": "built", "embedded": n, "seconds": round(time.time() - t0), **status(vault, con, cfg["model"])},
                         ensure_ascii=False))
        return 0
    print(json.dumps({"dense": "on", **status(vault, con, cfg["model"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
