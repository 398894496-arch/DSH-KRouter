#!/usr/bin/env python3
"""Pick one canonical row for a literal query. Exit 1 if none or ambiguous."""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

PARTICLES = set("的了着过地得")


def normalize(value: str) -> str:
    chars: list[str] = []
    for char in value:
        if char in PARTICLES or char.isspace():
            continue
        if unicodedata.category(char).startswith(("P", "S")):
            continue
        chars.append(char.lower())
    return "".join(chars)


def load_rows(path: Path) -> list[tuple[str, list[str], str, str]]:
    rows: list[tuple[str, list[str], str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("|", 3)
        if len(parts) != 4:
            raise ValueError(f"routing map row: {raw}")
        case_id, aliases_raw, source, anchor = parts
        aliases = [item.strip() for item in aliases_raw.split(";") if item.strip()]
        rows.append((case_id, aliases, source, anchor))
    return rows


def stands_in_for(q: str, a: str) -> bool:
    """A query shorter than the alias may stand in for it only when it is most of it.

    `how` sits inside `how to handle clippings` without meaning it, so a latin
    fragment has to carry the alias. One CJK character already carries a word.
    """
    if all(ord(char) < 128 for char in q):
        return len(q) >= 4 and len(q) * 2 >= len(a)
    return len(q) >= 2


def alias_score(query: str, alias: str) -> int:
    q = normalize(query)
    a = normalize(alias)
    if not q or not a:
        return 0
    if a == q:
        return 1000 + len(a)
    if a in q:
        return 500 + len(a)
    if q in a and stands_in_for(q, a):
        return 100 + len(q)
    return 0


def near_score(query: str, alias: str) -> int:
    """Weaker overlap for suggestions only. Never used as a canonical hit."""
    hit = alias_score(query, alias)
    if hit:
        return hit
    q = normalize(query)
    a = normalize(alias)
    if len(q) < 2 or len(a) < 2:
        return 0
    n = 0
    for left, right in zip(q, a):
        if left != right:
            break
        n += 1
    if n >= 2:
        return 40 + n
    overlap = len(set(q) & set(a))
    if overlap >= 2:
        return 20 + overlap
    return 0


def scores_for(query: str, rows: list[tuple[str, list[str], str, str]]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for case_id, aliases, _source, _anchor in rows:
        best = 0
        for alias in aliases:
            best = max(best, alias_score(query, alias))
        if best:
            scores[case_id] = best
    return scores


def pick(scores: dict[str, int], source_by_id: dict[str, str]) -> str | None:
    if not scores:
        return None
    top = max(scores.values())
    winners = [case_id for case_id, score in scores.items() if score == top]
    if len(winners) == 1:
        return winners[0]
    if len({source_by_id[case_id] for case_id in winners}) == 1:
        return sorted(winners)[0]
    return None


def lookup(query: str, rows: list[tuple[str, list[str], str, str]]) -> tuple[str, str, str] | None:
    source_by_id = {case_id: source for case_id, _aliases, source, _anchor in rows}
    winner = pick(scores_for(query, rows), source_by_id)
    if winner is None:
        token_scores: dict[str, int] = {}
        for token in query.split():
            for case_id, score in scores_for(token, rows).items():
                token_scores[case_id] = token_scores.get(case_id, 0) + score
        winner = pick(token_scores, source_by_id)
    if winner is None:
        return None
    for case_id, _aliases, source, anchor in rows:
        if case_id == winner:
            return case_id, source, anchor
    return None


def suggestions(
    query: str,
    rows: list[tuple[str, list[str], str, str]],
    limit: int = 5,
) -> list[tuple[int, str, str, str]]:
    ranked: list[tuple[int, str, str, str]] = []
    for case_id, aliases, source, _anchor in rows:
        best = 0
        best_alias = aliases[0] if aliases else ""
        for alias in aliases:
            score = near_score(query, alias)
            if score > best:
                best = score
                best_alias = alias
        if best:
            ranked.append((best, case_id, best_alias, source))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--suggest", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    rows = load_rows(Path(args.map))
    vault = Path(args.vault)

    if args.suggest:
        if not args.query:
            return 2
        for score, case_id, alias, relative_source in suggestions(args.query, rows, args.limit):
            source = vault / relative_source
            if not source.is_file():
                continue
            sys.stdout.write(f"{case_id}|{alias}|{relative_source}|{score}\n")
        return 0

    if not args.query:
        return 2
    hit = lookup(args.query, rows)
    if hit is None:
        return 1
    case_id, relative_source, anchor = hit
    source = vault / relative_source
    if not source.is_file():
        print(f"Canonical source missing: {source}", file=sys.stderr)
        return 1
    sys.stdout.write(f"{case_id}|{relative_source}|{anchor}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
