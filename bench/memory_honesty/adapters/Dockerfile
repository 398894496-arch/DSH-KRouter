# Third-party memory systems run here, not on the host: a container does not share the host's keychain, launchd or
# home directory (claude-mem, run under a separate HOME on macOS, still looked up the host's Claude Code login in the
# keychain). Build and run from the repository root:
#
#   docker build -f bench/memory_honesty/adapters/Dockerfile -t krouter-bench .
#   docker run --rm -v "$PWD/bench-out:/out" krouter-bench
#
# basic-memory 0.23 turns on semantic search by default and downloads its embedding model on first use. To run
# offline (`--network none`), download `BAAI/bge-small-en-v1.5` with fastembed on the host and mount the cache:
#   -e HF_HUB_OFFLINE=1 -v "$CACHE:/tmp/home/.basic-memory/fastembed_cache"
#
# It indexes each bench vault as its own basic-memory project and writes its scored answers for the sets named on
# the command line (default `dev heldout`; e.g. `docker run … krouter-bench dev3 heldout3`) to /out; grade them with
# bench/memory_honesty/run.py --answers and bench/memory_honesty/floor.py.
FROM python:3.13-slim
ARG BASIC_MEMORY_VERSION=0.23.2
# 只在需要代理才能连 PyPI 时传：--build-arg PIP_PROXY=http://…
ARG PIP_PROXY=
RUN pip install --no-cache-dir "basic-memory==${BASIC_MEMORY_VERSION}"
WORKDIR /bench
COPY bench/memory_honesty /bench/memory_honesty
ENV HOME=/tmp/home
ENTRYPOINT ["/bin/sh", "-c", "set -e; mkdir -p /out \"$HOME\"; \
    for v in vault vault2 vault3; do \
      basic-memory project add \"$v\" \"/bench/memory_honesty/$v\" >/dev/null; \
      basic-memory reindex --project \"$v\" >/dev/null; \
    done; \
    for s in ${@:-dev heldout}; do \
      case $s in dev3|heldout2) v=vault2;; heldout3) v=vault3;; *) v=vault;; esac; \
      python3 /bench/memory_honesty/adapters/basic_memory.py --set \"$s\" --project \"$v\" > \"/out/basic-memory.$s.jsonl\"; \
    done; \
    basic-memory --version 2>/dev/null || pip show basic-memory | grep -i ^version; echo done", "sh"]
