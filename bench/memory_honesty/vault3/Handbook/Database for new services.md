---
title: Database for new services
status: active
supersedes: "[[Database for new services (old)]]"
date: 2026-09-20
---

# Database for new services

New services use PostgreSQL 16; MySQL stays only for the legacy billing system. Each service owns its schema, and there are no joins across services. Changed to run a single database engine. This replaces [[Database for new services (old)]].
