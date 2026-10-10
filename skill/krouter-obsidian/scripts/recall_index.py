#!/usr/bin/env python3
"""L1 recall: a rebuildable SQLite FTS5 cache over the vault's Markdown.

The lock (canonical_lookup) stays the only thing that may claim a page. Recall only ranks.
Text is pre-split into CJK bigrams and latin words, so FTS5's own bm25() does the scoring.
The cache lives outside the vault, follows file mtimes, and can be deleted at any time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

SCHEMA_VERSION = "recall-v6"
STRONG_W = 0.5  # 软权重 ≥ 此值才算"有效匹配词"
MIN_STRONG_MATCH = 2
SCORE_MIN = 8.5  # bm25×分层权重的绝对下限
SINGLE_TERM_SCORE = 25.0  # 只有一个有效词时，分数要高到这个程度才回答
# 双字"像词"的下限：df(xy)/min(df(x),df(y))；跨词边界的拼接双字通常 < 0.1
WORDNESS_MIN = 0.12
STATUS_LINE_RE = re.compile(r"^(active|provisional|candidate|superseded|retired|rejected|status|状态)\b", re.I)
SKIP_PARTS = {"Clippings", ".trash", ".obsidian", "迁移备份", "node_modules", ".git"}
RULE_PREFIXES = (
    "02 经验与方法/",
    "90 系统文件/Agent记忆/",
    "90 系统文件/自动化/",
)
RULE_FILES = {"AGENTS.md", "Agent第二大脑.md", "01 项目/项目.md"}
DEAD_STATUS = {"superseded", "retired", "rejected", "deprecated", "archived"}
HOW_MAX = 80
# 问句里的功能性双字，几乎每页都有，不参与召回
QUERY_STOP = {
    "什么", "怎么", "怎样", "能不", "不能", "是不", "不是", "哪个", "哪些", "哪里", "应该",
    "可以", "现在", "到底", "一下", "我的", "我们", "你的", "为什", "么要", "有没", "没有",
    "是什", "么样", "要不", "不要", "还是", "这个", "那个", "如何", "多少", "吗我",
}
CJK_RE = re.compile(r"[㐀-鿿豈-﫿]+")
LATIN_RE = re.compile(r"[a-z0-9]+")  # 与 FTS5 unicode61 的切分一致


def cache_path(vault: Path) -> Path:
    base = Path(os.environ.get("KROUTER_CACHE_DIR") or Path.home() / ".cache" / "krouter")
    digest = hashlib.sha1(str(vault.resolve()).encode("utf-8")).hexdigest()[:12]
    return base / f"recall-{digest}.sqlite"


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "").lower()
    out: list[str] = []
    for run in CJK_RE.findall(text):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    out.extend(w for w in LATIN_RE.findall(text) if len(w) >= 2)
    return out


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "-", "\t")):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4 :].lstrip("-\n")


def unigrams(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return sorted({c for run in CJK_RE.findall(text) for c in run})


def _clean(line: str) -> str:
    line = re.sub(r"^(>\s*(\[![^\]]+\]\s*)?|[-*+]\s+|\d+\.\s+)", "", line.strip())
    return re.sub(r"[*`_]|\[\[([^|\]]*\|)?|\]\]", "", line).strip()


def first_rule_line(body: str) -> str:
    plain = ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", "```", "<", "![", "%%")):
            continue
        cleaned = _clean(line)
        if len(cleaned) < 8 or STATUS_LINE_RE.match(cleaned):
            continue
        if "**" in line:
            # 准纠错/方法页的第一条加粗规则就是结论
            text = cleaned
            return text[: HOW_MAX - 1] + "…" if len(text) > HOW_MAX else text
        if not plain:
            plain = cleaned
    return plain[: HOW_MAX - 1] + "…" if len(plain) > HOW_MAX else plain


TRIGGER_GLOB = "下意识触发词*.psv"  # 人工/生成的触发词 + 夜间自学习的触发词


def alias_map(vault: Path | None = None) -> tuple[dict[str, list[str]], str]:
    """页面的召回触发词：人工锁别名（canonical_sources.psv）+ 90 系统文件/ 下的旁路 `下意识触发词.psv`（rel|词;词）。

    只用于召回排序，不参与锁定；锁定仍只认人工别名表。
    """
    raw = os.environ.get("KROUTER_MAP") or str(Path(__file__).resolve().parent / "canonical_sources.psv")
    sources = [Path(raw)]
    if vault is not None and (vault / "90 系统文件").is_dir():
        sources += sorted((vault / "90 系统文件").rglob(TRIGGER_GLOB))
    out: dict[str, list[str]] = {}
    digest = hashlib.sha1()
    for path in sources:
        if not path.is_file():
            continue
        data = path.read_bytes()
        digest.update(data)
        for line in data.decode("utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) == 4:  # canonical map: id|aliases|source|anchor
                rel, words = parts[2], parts[1]
            elif len(parts) == 2:  # trigger sidecar: rel|words
                rel, words = parts
            else:
                continue
            out.setdefault(rel.strip(), []).extend(a.strip() for a in words.split(";") if a.strip())
    return out, digest.hexdigest()


def tier_of(rel: str, status: str) -> str:
    if status in DEAD_STATUS or status == "generated":
        return "dead"
    if rel in RULE_FILES or rel.startswith(RULE_PREFIXES) or ("协作/" in rel and rel.startswith("90 系统文件/")):
        return "rule"
    if rel.startswith("05 时间日志/"):
        return "log"
    if rel.startswith("01 项目/") or rel.startswith("04 已完成与复盘/"):
        return "project"
    return "other"


def iter_markdown(vault: Path):
    for root, dirs, files in os.walk(vault, followlinks=True):
        dirs[:] = [d for d in dirs if d not in SKIP_PARTS and not d.startswith(".")]
        for name in files:
            if name.endswith(".md"):
                path = Path(root) / name
                yield path, path.relative_to(vault).as_posix()


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    row = con.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
    if not row or row[0] != SCHEMA_VERSION:
        con.executescript(
            """
            DROP TABLE IF EXISTS vcol; DROP TABLE IF EXISTS vinst; DROP TABLE IF EXISTS vrow; DROP TABLE IF EXISTS docs; DROP TABLE IF EXISTS files;
            CREATE VIRTUAL TABLE docs USING fts5(
                rel UNINDEXED, title, triggers, body, uni, tier UNINDEXED, status UNINDEXED, how UNINDEXED,
                tokenize='unicode61');
            CREATE VIRTUAL TABLE vrow USING fts5vocab(docs, 'row');
            CREATE VIRTUAL TABLE vinst USING fts5vocab(docs, 'instance');
            CREATE VIRTUAL TABLE vcol USING fts5vocab(docs, 'col');
            CREATE TABLE files(rel TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER, rid INTEGER);
            """
        )
        con.execute("INSERT OR REPLACE INTO meta VALUES('schema', ?)", (SCHEMA_VERSION,))
        con.commit()
    return con


def refresh(vault: Path, con: sqlite3.Connection) -> dict[str, int]:
    seen: dict[str, tuple[int, int, Path]] = {}
    for path, rel in iter_markdown(vault):
        try:
            st = path.stat()
        except OSError:
            continue
        seen[rel] = (st.st_mtime_ns, st.st_size, path)
    known = {rel: (m, s, rid) for rel, m, s, rid in con.execute("SELECT rel, mtime_ns, size, rid FROM files")}
    aliases, map_sha = alias_map(vault)
    old_sha = (con.execute("SELECT v FROM meta WHERE k='map_sha'").fetchone() or [""])[0]
    if map_sha != old_sha:
        # 别名或触发词变了：全部重建（一次约 1–2 秒），避免被删掉的触发词残留
        known = {rel: (-1, s, rid) for rel, (_m, s, rid) in known.items()}
        con.execute("INSERT OR REPLACE INTO meta VALUES('map_sha', ?)", (map_sha,))
    changed = added = removed = 0
    for rel, (_m, _s, rid) in known.items():
        if rel not in seen:
            con.execute("DELETE FROM docs WHERE rowid=?", (rid,))
            con.execute("DELETE FROM files WHERE rel=?", (rel,))
            removed += 1
    for rel, (mtime, size, path) in seen.items():
        old = known.get(rel)
        if old and old[0] == mtime and old[1] == size:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = split_frontmatter(text)
        title = meta.get("title") or path.stem
        status = (meta.get("status") or "").lower()
        trig = " ".join([meta.get("triggers") or meta.get("aliases") or ""] + aliases.get(rel, []))
        how = meta.get("how") or first_rule_line(body)
        dirs = " ".join(rel.split("/")[:-1])
        if old:
            con.execute("DELETE FROM docs WHERE rowid=?", (old[2],))
            changed += 1
        else:
            added += 1
        cur = con.execute(
            "INSERT INTO docs(rel, title, triggers, body, uni, tier, status, how) VALUES(?,?,?,?,?,?,?,?)",
            (
                rel,
                " ".join(tokens(title + " " + path.stem)),
                " ".join(tokens(trig)),
                " ".join(tokens(dirs + "\n" + body)),
                " ".join(unigrams(title + " " + trig + " " + body)),
                tier_of(rel, status),
                status,
                how,
            ),
        )
        con.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?)", (rel, mtime, size, cur.lastrowid))
    if changed or added or removed:
        con.execute("INSERT OR REPLACE INTO meta VALUES('built_at', ?)", (time.strftime("%Y-%m-%dT%H:%M:%S"),))
        con.commit()
    return {"added": added, "changed": changed, "removed": removed, "docs": len(seen)}


TIER_BOOST = {"rule": 1.6, "project": 1.0, "other": 0.9, "log": 0.8, "dead": 0.25}


def recall(vault: Path, query: str, scope: str = "", limit: int = 5, refresh_first: bool = True,
           gate: bool = True) -> dict:
    con = connect(cache_path(vault))
    stats = refresh(vault, con) if refresh_first else {}
    raw: list[str] = []
    for t in tokens(query):
        if t not in QUERY_STOP and t not in raw:
            raw.append(t)
    if not raw:
        return {"hits": [], "stats": stats, "query_tokens": [], "confidence": "none", "margin": 0.0}
    df = term_df(con, raw + [c for t in raw if is_cjk_bigram(t) for c in t])
    present = [t for t in raw if df.get(t, 0) > 0]
    named = phrase_terms(con, [t for t in present if is_cjk_bigram(t)])
    qtok = [t for t in present if not is_cjk_bigram(t) or t in named or wordness(t, df) >= WORDNESS_MIN] or present
    if not qtok:
        return {"hits": [], "stats": stats, "query_tokens": [], "confidence": "none", "margin": 0.0}
    match = "{title triggers body} : (" + " OR ".join('"' + t.replace('"', "") + '"' for t in qtok) + ")"
    rows = con.execute(
        "SELECT rowid, rel, tier, status, how, bm25(docs, 0, 4.0, 4.0, 1.0, 0, 0, 0, 0) AS s "
        "FROM docs WHERE docs MATCH ? ORDER BY s LIMIT 80",
        (match,),
    ).fetchall()
    scope = scope.strip("/")
    hits = []
    for rid, rel, tier, status, how, s in rows:
        if scope and not (rel == scope or rel.startswith(scope + "/")):
            continue
        hits.append({"rid": rid, "rel": rel, "tier": tier, "status": status, "how": how,
                     "score": round(-s * TIER_BOOST.get(tier, 1.0), 3)})
    hits.sort(key=lambda h: -h["score"])
    hits = hits[:limit]
    if not hits:
        return {"hits": [], "stats": stats, "query_tokens": qtok, "confidence": "none", "margin": 0.0}
    strong = strong_matches(con, hits[0]["rid"], present, df, named)
    top = hits[0]["score"]
    second = hits[1]["score"] if len(hits) > 1 else 0.0
    margin = top / second if second else 9.9
    # bm25 的量级随库大小变化：小库按文档数等比缩放下限，千篇以上用满额
    n_docs = con.execute("SELECT count(*) FROM files").fetchone()[0] or 1
    scale = min(1.0, n_docs / 1000)
    # 关键词式查询（`DSH`、`SyGJ`）本身只有一个实词，命中它就够；整句问题仍要求至少两个实词
    need = min(MIN_STRONG_MATCH, query_content_terms(raw, df, named))
    if gate and (top < SCORE_MIN * scale or (strong < need and top < SINGLE_TERM_SCORE * scale) or strong == 0):
        conf = "none"
    elif margin >= 1.5 and hits[0]["tier"] == "rule":
        conf = "high"
    elif margin >= 1.15:
        conf = "medium"
    else:
        conf = "low"
    for h in hits:
        h.pop("rid", None)
    return {"hits": hits, "stats": stats, "query_tokens": qtok, "margin": round(margin, 2),
            "strong": strong, "confidence": conf}


def strong_matches(con: sqlite3.Connection, rid: int, terms: list[str], df: dict[str, int],
                   named: set[str] = frozenset()) -> int:
    """首条命中页里出现了几个"像词"的查询词。只碰上一个泛词的，多半是巧合。"""
    if not terms:
        return 0
    marks = ",".join("?" * len(terms))
    hit = {t for (t,) in con.execute(
        f"SELECT DISTINCT term FROM vinst WHERE term IN ({marks}) AND doc = ? AND col IN ('title','triggers','body')",
        terms + [rid],
    )}
    # 纯数字（年份、日期、序号）到处都有，只参与排序，不算实词
    return sum(1 for t in hit if (soft_weight(t, df) >= STRONG_W or t in named) and not t.isdigit())


def query_content_terms(raw: list[str], df: dict[str, int], named: set[str] = frozenset()) -> int:
    """问题里有几个实词：拉丁词、像词的双字；库里没有但由少见字组成的双字也算（说明问的是库外的东西）。"""
    n = 0
    for t in raw:
        if not is_cjk_bigram(t):
            n += len(t) >= 2 and not t.isdigit()
        elif df.get(t, 0) > 0:
            n += soft_weight(t, df) >= STRONG_W or t in named
        else:
            n += min(df.get(t[0], 0), df.get(t[1], 0)) < 30
    return n


def soft_weight(t: str, df: dict[str, int]) -> float:
    """跨词拼接的双字降权而不删除，真词（含由常用字组成的少见词）保留部分分量。"""
    if not is_cjk_bigram(t):
        return 1.0
    return max(0.2, min(1.0, wordness(t, df) / 0.3))


def phrase_terms(con: sqlite3.Connection, terms: list[str]) -> set[str]:
    """出现在任意标题或触发词里的双字：这些短语是人或模型完整写出来的，跨词拼接的垃圾双字基本不会出现。"""
    if not terms:
        return set()
    marks = ",".join("?" * len(terms))
    return {t for (t,) in con.execute(
        f"SELECT DISTINCT term FROM vcol WHERE term IN ({marks}) AND col IN ('title','triggers')", terms)}


def is_cjk_bigram(t: str) -> bool:
    return len(t) == 2 and all(CJK_RE.fullmatch(c) for c in t)


def term_df(con: sqlite3.Connection, terms: list[str]) -> dict[str, int]:
    uniq = sorted(set(terms))
    if not uniq:
        return {}
    marks = ",".join("?" * len(uniq))
    return dict(con.execute(f"SELECT term, doc FROM vrow WHERE term IN ({marks})", uniq).fetchall())


def wordness(bigram: str, df: dict[str, int]) -> float:
    pair = df.get(bigram, 0)
    base = min(df.get(bigram[0], 0), df.get(bigram[1], 0))
    return pair / base if base else 0.0


def best_lines(path: Path, qtok: list[str], k: int = 1) -> list[tuple[int, str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    scored = []
    for i, line in enumerate(lines, 1):
        lt = set(tokens(line))
        n = sum(1 for t in qtok if t in lt)
        if n:
            scored.append((n, i, line.strip()[:160]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return sorted((i, text) for _n, i, text in scored[:k])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT", ""))
    ap.add_argument("--query", default="")
    ap.add_argument("--scope", default="", help="vault-relative dir or file to restrict to")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--lines", type=int, default=1, help="best matching lines to show per hit")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    if not args.vault:
        print("set OBSIDIAN_VAULT", file=sys.stderr)
        return 2
    vault = Path(args.vault)
    db = cache_path(vault)
    if args.rebuild and db.exists():
        db.unlink()
    if args.stats or not args.query:
        con = connect(db)
        st = refresh(vault, con)
        tiers = dict(con.execute("SELECT tier, count(*) FROM docs GROUP BY tier").fetchall())
        built = (con.execute("SELECT v FROM meta WHERE k='built_at'").fetchone() or [""])[0]
        print(json.dumps({"cache": str(db), "built_at": built, "tiers": tiers, **st}, ensure_ascii=False))
        return 0
    res = recall(vault, args.query, args.scope, args.limit)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print(f"recall_confidence: {res.get('confidence', 'none')}")
    print(f"recall_margin: {res.get('margin', 0)}")
    print(f"recall_strong_terms: {res.get('strong', 0)}")
    if not res["hits"] or res.get("confidence") == "none":
        print("recall: none (no page covers enough of the question; do not guess)")
        return 0
    print("recall:")
    for h in res["hits"]:
        flag = f" status={h['status']}" if h["status"] else ""
        print(f"- {h['rel']} tier={h['tier']}{flag} score={h['score']}")
        if h["how"]:
            print(f"  how: {h['how']}")
        for ln, text in best_lines(vault / h["rel"], res["query_tokens"], args.lines):
            print(f"  L{ln}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
