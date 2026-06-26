# 003 mempalace bring-up acid test — PROOF ENVIRONMENT, not a deployment target.
#
# A clean image that proves `mneme mp bringup` works end-to-end against the REAL
# mempalace(kostadis-dev) + turbovecdb, in two embedder modes (ONNX-local / LAN Qwen),
# against a throwaway $HOME/.mempalace — so the test never touches the operator's live
# campaign stores. Mirrors specs/001-reproducible-install/validation/.
#
# Unlike 001 (which proves the TOOL with no heavy components), this DOES install the
# real mempalace + turbovecdb — that is the point: prove the bring-up against real silicon.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/mneme

# The tool under test (built from the repo-root build context).
COPY pyproject.toml ./
COPY hypostasis/ ./hypostasis/
COPY mneme/ ./mneme/

# Install mneme + the REAL backend. turbovecdb + mempalace come from the kostadis forks;
# onnxruntime gives a self-contained local embedder (the ONNX lane needs no network).
# Pin refs match the versions hypostasis.yaml declares; adjust as those pins move.
RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir "git+https://github.com/kostadis/turbovecdb@fea4d804b5bbc744c17afcf3e7a75f6e7c9edb49" \
    && pip install --no-cache-dir "git+https://github.com/kostadis/mempalace@46fcfc2adf50e31f68889edaf8965a7cb2adcfff" \
    && pip install --no-cache-dir onnxruntime

# Last (so editing the acid test does not invalidate the pip layer).
COPY specs/003-new-campaign-mempalace/validation/run-validation.sh ./validation/run-validation.sh

ENV EMBEDDER=onnx
ENTRYPOINT ["bash", "/opt/mneme/validation/run-validation.sh"]
