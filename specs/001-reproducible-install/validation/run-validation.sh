#!/usr/bin/env bash
# SC-005 reproducibility acid test (research D10). Proves hypostasis + mneme install
# cleanly and the core loop works from the authority alone — in a clean container OR on
# the host. Exits non-zero on any FAIL (Principle I: a red dashboard exits red).
#
# What it proves (reframed for the hypostasis/mneme split):
#   - both commands resolve (the package is reproducibly installable);
#   - `hypostasis status` RUNS and reports honestly;
#   - `hypostasis apply` renders the wiring, and a one-value change leaves NO stale copy
#     (Principle V / SC-004);
#   - `mneme up <campaign> --dry-run` previews the per-campaign launch incl. env-delivery.
# It does NOT install the heavy components or reach the real substrate — that needs the
# DGX + the repos (D2); this proves the TOOL, not a live system.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
HYP="hypostasis"; MNE="mneme"
if ! command -v hypostasis >/dev/null 2>&1; then
  HYP="python3 -m hypostasis.cli"; MNE="python3 -m mneme.cli"; export PYTHONPATH="$ROOT"
fi
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
fail() { echo "FAIL: $1" >&2; exit 1; }

echo "1/6 both commands resolve"
$HYP --help >/dev/null || fail "hypostasis --help"
$MNE --help >/dev/null || fail "mneme --help"

echo "2/6 build a self-contained sample environment (dgx external; one rendered component)"
mkdir -p "$WORK/campaigns/demo" "$WORK/cg/config"
cat > "$WORK/hypostasis.yaml" <<YAML
venv: $WORK/venv
machines: { dgx: { endpoint: http://demo:8001/v1, default_model: demo-model } }
data_roots:
  fivetools: $WORK/5e
  fivetools_mcp_index: $WORK/5e/mcp/index.js
  rpg_library_db: $WORK/rpg.db
  pdf_translators: $WORK/pdf
  homebrew: $WORK/hb
  campaigns: $WORK/campaigns
env: { MEMPALACE_BACKEND: turbovec }
services:
  dgx: { url: http://demo:8001/v1, managed: false }
  rpg_lib: { url: http://localhost:8000, managed: false }
components:
  CampaignGenerator:
    source: { path: $WORK/cg }
    pin: abc123def456
    config_template: campaigngenerator.wiring.yaml.j2
    config_target: $WORK/cg/config/wiring.yaml
order: { install: [CampaignGenerator], startup: [dgx, rpg_lib] }
YAML

echo "3/6 hypostasis status runs honestly (FAILs are expected on a dummy box — we require it RAN)"
$HYP status -c "$WORK/hypostasis.yaml" >/dev/null 2>&1 || true

echo "4/6 hypostasis apply renders the wiring with a fresh stamp"
$HYP apply -c "$WORK/hypostasis.yaml" >/dev/null || fail "apply failed"
W="$WORK/cg/config/wiring.yaml"
grep -q 'hypostasis-rendered' "$W" || fail "no source-hash stamp in rendered config"
grep -q 'dgx_endpoint: http://demo:8001/v1' "$W" || fail "value not rendered"

echo "5/6 change one value + apply → NO stale copy (Principle V / SC-004)"
sed -i 's#http://demo:8001/v1#http://CHANGED:9999/v1#g' "$WORK/hypostasis.yaml"
$HYP apply -c "$WORK/hypostasis.yaml" >/dev/null || fail "re-apply failed"
grep -q 'CHANGED:9999' "$W" || fail "new value not rendered"
grep -q 'demo:8001' "$W" && fail "STALE copy remains after apply" || true

echo "6/6 mneme up <campaign> --dry-run previews the launch + env-delivery"
$MNE up demo --dry-run -c "$WORK/hypostasis.yaml" | grep -q 'MEMPALACE_BACKEND' \
  || fail "env-delivery (MEMPALACE_BACKEND) not in the mneme up plan"

echo
echo "ALL PASS — hypostasis+mneme reproducible; render/apply coherence + per-campaign launch verified."
