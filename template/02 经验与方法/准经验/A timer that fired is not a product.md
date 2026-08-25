---
title: A timer that fired is not a product
type: method
status: provisional
memory_class: method
confidence: 0.86
source_kind: runtime-observation
source_ref: "[[05 时间日志/2026-01/01｜示例日]]"
valid_from: 2026-01-01
verified_at: 2026-01-01
next_ask: ask before answering "did the scheduled job run" from the scheduler alone
last_change_writer: template
---

# A timer that fired is not a product

Cron or launchd waking up, and a session reporting `task_complete`, only prove the scheduler is alive.

Whether the work happened is a separate check, and it takes three answers:

1. Does the file for the target day exist on disk?
2. Was the health or status page updated?
3. On failure, was a gap left on purpose (a to-summarize note) instead of a silent skip?

## Evidence

The sample day was woken on time and the session closed clean, yet the day's note was still the to-summarize stub. The scheduler was healthy; the day was not sealed.

## Limits

Applies to unattended scheduled jobs. It does not cover files a person asked for and watched land during an interactive session.

## Why this is still a draft

This page was written the same day the five gates passed, so it is `provisional`. It becomes a formal method only when the next similar task asks the host, the host adopts it, and that task is accepted. Until then, treat it as a draft you may quote, not a rule you enforce.
