# SC-005 reproducibility acid test — PROOF ENVIRONMENT, not a deployment target.
# Skeleton: encodes intent; completed in /speckit.implement once the `platform` CLI exists.
#
# The point: a clean image has NO pre-existing venv, NO ~/src checkouts, NO host state.
# If `platform install` brings the system up from platform.yaml alone in here, the
# Infrastructure-Proxy constants (II) and Fragmented-State config (III) are proven
# externalized — not a configured-box illusion.

FROM python:3.11-slim

# git: fetch component sources at their pinned refs. No other host state is copied in.
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/platform

# Bring in ONLY the manager (the platform CLI) + the single authority. Everything else
# the system needs is resolved by `platform install` from platform.yaml — that is the test.
#   COPY platform/ ./platform/
#   COPY pyproject.toml ./
#   COPY platform.yaml ./                # the validation platform.yaml (pins = git refs)
# RUN pip install --no-cache-dir .       # install the manager itself

# Canonical ports are safe here: separate network namespace, no host conflict.
#   8000 rpg-lib, 8077 turbovecdb-service

# DGX endpoint mode is injected at run time (see compose): real | stub.
ENV DGX_MODE=stub

# Entrypoint runs the full honesty loop and exits non-zero on any FAIL (Principle I):
#   platform install \
#     && platform up \
#     && platform status \
#     && sed -i 's/<old-ip>/<new-ip>/' platform.yaml && platform apply && platform status
# ENTRYPOINT ["/opt/platform/validation/run-validation.sh"]
