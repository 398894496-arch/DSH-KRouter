---
title: Container base image
status: active
supersedes: "[[Container base image (old)]]"
date: 2026-09-15
---

# Container base image

Build every service image on distroless/base-debian12. Images based on ubuntu fail the CI image scan. Changed after the scanner reported 40 high-severity packages we never used. This replaces [[Container base image (old)]].
