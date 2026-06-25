# SC-005 reproducibility acid test — PROOF ENVIRONMENT, not a deployment target.
#
# A clean image with NO pre-existing venv, NO ~/src checkouts, NO host state. If
# `pip install .` yields working `hypostasis` + `mneme` commands and the
# config→render→apply→status loop runs from the authority alone, the tool is
# reproducibly installable and the Principle-V coherence holds — not a configured-box
# illusion. (It does NOT install the heavy components or reach the real substrate —
# that needs the DGX + the repos; D2. This proves the TOOL.)

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/hypostasis

# Bring in ONLY the tool (both commands) + its packaging. No host venv/checkouts/state.
COPY pyproject.toml ./
COPY hypostasis/ ./hypostasis/
COPY mneme/ ./mneme/
COPY specs/001-reproducible-install/validation/run-validation.sh ./validation/run-validation.sh

# Proves the package installs cleanly → `hypostasis` + `mneme` land on PATH (with the
# shipped templates as package-data).
RUN pip install --no-cache-dir .

# The acid test runs the loop from the authority alone and exits non-zero on any FAIL.
ENTRYPOINT ["bash", "/opt/hypostasis/validation/run-validation.sh"]
