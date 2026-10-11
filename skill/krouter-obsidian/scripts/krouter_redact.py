#!/usr/bin/env python3
"""Secrets never leave the vault through KRouter: not to a model, not into an agent's context, not into the cache.

Two layers. By path: the key page (`90 系统文件/自动化/自进化钥匙.md`, wherever zones map it) is never sent to
a model and never quoted. By content, everywhere else: every text KRouter prints, indexes, logs or sends goes
through `redact()`, which replaces values of key-like assignments (`DEEPSEEK_API_KEY=sk-…`, `token: …`,
`password = …`), well-known key shapes (`sk-…`, `ghp_…`, `AKIA…`, `AIza…`, `xox…`, `hf_…`, …) and bearer tokens
with `<redacted>`. Placeholders (`YOUR_…`, `CHANGE_ME`, `<…>`) stay readable so the page still explains itself.
"""

from __future__ import annotations

import re

SECRET_PAGES = ("90 系统文件/自动化/自进化钥匙.md",)
MARK = "<redacted>"
PLACEHOLDER = re.compile(r"^(?:YOUR_|CHANGE_?ME|REPLACE|TODO|PASTE_|sk-your|x{4,}|<|\.\.\.|…)", re.I)
ASSIGN = re.compile(
    r"(?P<k>\b[A-Za-z0-9_]*(?:API[_-]?KEY|APIKEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD)"
    r"[A-Za-z0-9_]*[\"']?\s*[:=]\s*[\"']?)(?P<v>[^\s\"'`,;|)）]+)", re.I)
KNOWN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-(?:ant-|proj-|or-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|glpat-[A-Za-z0-9_-]{20,}"
    r"|hf_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,})")
BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{16,}")


def _value_is_secret(v: str) -> bool:
    if PLACEHOLDER.match(v) or v == MARK:
        return False
    has_alpha, has_digit = re.search(r"[A-Za-z]", v), re.search(r"\d", v)
    # `tokens: 158386`（用量数字）不是密钥；钥匙要么够长，要么字母数字混排
    return (len(v) >= 12 and not v.isdigit()) or (len(v) >= 6 and bool(has_alpha and has_digit))


def redact(text: str) -> str:
    if not text:
        return text
    text = ASSIGN.sub(lambda m: m.group("k") + (MARK if _value_is_secret(m.group("v")) else m.group("v")), text)
    text = KNOWN.sub(MARK, text)
    return BEARER.sub(r"\1" + MARK, text)


def is_secret_page(canon_rel: str) -> bool:
    """`canon_rel` is the default-layout path (zones.canon)."""
    return canon_rel in SECRET_PAGES


if __name__ == "__main__":  # filter: `… | python3 krouter_redact.py` (the shell router's literal search)
    import sys

    for line in sys.stdin:
        sys.stdout.write(redact(line))
