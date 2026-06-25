# SC-005 reproducibility acid test — PROOF ENVIRONMENT, not a deployment target.
# Skeleton: encodes intent; completed in /speckit.implement once the `hypostasis` CLI exists.
#
# The point: a clean image has NO pre-existing venv, NO ~/src checkouts, NO host state.
# If `hypostasis install` brings the system up from hypostasis.yaml alone in here, the
# Infrastructure-Proxy constants (II) and Fragmented-State config (III) are proven
# externalized — not a configured-box illusion.

FROM python:3.11-slim

# git: fetch component sources at their pinned refs. No other host state is copied in.
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/mneme

# Bring in ONLY the manager (the mneme CLI) + the single authority. Everything else
# the system needs is resolved by `hypostasis install` from hypostasis.yaml — that is the test.
#   COPY mneme/ ./mneme/
#   COPY pyproject.toml ./
#   COPY hypostasis.yaml ./                # the validation hypostasis.yaml (pins = git refs)
# RUN pip install --no-cache-dir .       # install the manager itself

# Canonical ports are safe here: separate network namespace, no host conflict.
#   8000 rpg-lib, 8077 turbovecdb-service

# DGX endpoint mode is injected at run time (see compose): real | stub.
ENV DGX_MODE=stub

# Entrypoint runs the full honesty loop and exits non-zero on any FAIL (Principle I):
#   mneme install \
#     && mneme up \
#     && mneme status \
#     && sed -i 's/<old-ip>/<new-ip>/' hypostasis.yaml && mneme apply && mneme status
# ENTRYPOINT ["/opt/mneme/validation/run-validation.sh"]
