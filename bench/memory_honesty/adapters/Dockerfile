# Third-party memory systems run here, not on the host: a container does not share the host's keychain, launchd or
# home directory (claude-mem, run under a separate HOME on macOS, still looked up the host's Claude Code login in the
# keychain). Build and run from the repository root:
#
#   docker build -f bench/memory_honesty/adapters/Dockerfile -t krouter-bench .
#   docker run --rm -v "$PWD/bench-out:/out" krouter-bench
#
# It indexes the bench vault with basic-memory and writes its scored answers for both sets to /out; grade them with
# bench/memory_honesty/run.py --answers and bench/memory_honesty/floor.py.
FROM python:3.13-slim
RUN pip install --no-cache-dir basic-memory==0.22.1
WORKDIR /bench
COPY bench/memory_honesty /bench/memory_honesty
ENV HOME=/tmp/home
CMD set -e; mkdir -p /out "$HOME"; \
    basic-memory project add bench /bench/memory_honesty/vault >/dev/null; \
    basic-memory project default bench >/dev/null; \
    basic-memory reindex --project bench >/dev/null; \
    for s in dev heldout; do python3 /bench/memory_honesty/adapters/basic_memory.py --set "$s" > "/out/basic-memory.$s.jsonl"; done; \
    echo done
