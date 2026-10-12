---
title: Password hashing
status: active
supersedes: "[[Password hashing (old)]]"
date: 2026-09-15
---

# Password hashing

Hash user passwords with argon2id using 64 MB of memory and 3 iterations. Existing bcrypt hashes are rehashed with argon2id at the user's next login. Changed after the security audit in August. This replaces [[Password hashing (old)]].
