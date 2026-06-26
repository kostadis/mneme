#!/usr/bin/env bash
# 003 mempalace bring-up acid test (proof environment). Runs the REAL mempalace +
# turbovecdb bring-up against a throwaway $HOME/.mempalace, in EMBEDDER=onnx|qwen.
# Exits non-zero on any FAIL (Principle I: a red dashboard exits red). Runs in the
# container OR on the host. Proves the bring-up mechanics against real silicon.
set -euo pipefail

EMBEDDER="${EMBEDDER:-onnx}"
export HOME="$(mktemp -d)"          # throwaway store — never the operator's ~/.mempalace
export MEMPALACE_BACKEND=turbovec
ROOTBASE="$(mktemp -d)"
ROOT="$ROOTBASE/campaigns"
CAMP="$ROOT/acidcamp"
STORE="$HOME/.mempalace/palaces/acidcamp"
CONFIG=""

# Always delete the temporary mempalace + campaigns + config on exit (a fresh, isolated
# store per run; nothing persists, nothing touches the operator's real ~/.mempalace).
cleanup() { rm -rf "$HOME" "$ROOTBASE" "$CONFIG" 2>/dev/null || true; }
trap cleanup EXIT

echo "== 003 acid test (EMBEDDER=$EMBEDDER, HOME=$HOME) =="

# Embedder wiring (with vs without the Qwen substrate).
if [ "$EMBEDDER" = "qwen" ]; then
  export MEMPALACE_EMBEDDING_PROVIDER=openai-compat
  : "${MEMPALACE_EMBEDDING_ENDPOINT:?qwen lane needs MEMPALACE_EMBEDDING_ENDPOINT}"
  # Health-gate the substrate first (never assume up — Principle I).
  curl -fsS "${MEMPALACE_EMBEDDING_ENDPOINT%/}/v1/models" >/dev/null 2>&1 \
    || curl -fsS "$MEMPALACE_EMBEDDING_ENDPOINT" >/dev/null 2>&1 \
    || { echo "FAIL: embedding substrate not up at $MEMPALACE_EMBEDDING_ENDPOINT"; exit 2; }
else
  export MEMPALACE_EMBEDDING_PROVIDER=onnx
fi

# A sample greenfield campaign (documents, no .mneme/) + a minimal hypostasis.yaml.
mkdir -p "$CAMP/docs/chapters"
printf '# Chapter 1\nThe vault opens; the lantern gutters.\n' > "$CAMP/docs/chapters/ch01.md"
printf '# World\nThe city of Acid stands on a salt flat.\n' > "$CAMP/world.md"
CONFIG="$(mktemp)"
cat > "$CONFIG" <<YAML
venv: $HOME/venv
machines: { dgx: { endpoint: http://localhost:1/v1 } }
services: { dgx: { url: http://localhost:1/v1, managed: false } }
components:
  mempalace: { source: { path: $HOME }, pin: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef }
order: { install: [mempalace], startup: [dgx] }
data_roots: { campaigns: $ROOT }
YAML
# `--config` is a per-subcommand option (goes AFTER the subcommand); `--palace` is a
# GLOBAL mempalace option (goes BEFORE the subcommand).
CFG=(--config "$CONFIG")

fail() { echo "FAIL: $1"; exit 1; }

echo "-- bringup --"
mneme mp bringup acidcamp --no-backup "${CFG[@]}"
[ -f "$STORE/turbovec/mempalace_drawers/store.sqlite3" ] || fail "store not created"
grep -q '^palace: acidcamp' "$CAMP/mempalace.yaml" || fail "cli_pointer face missing palace:"
grep -q 'acidcamp' "$HOME/.mempalace/config.json" || fail "global alias not registered"

echo "-- search returns over the sample docs --"
mempalace --palace "$STORE" search "vault" | grep -qi vault || fail "search returned nothing"

echo "-- backup excludes rebuildable/legacy --"
mneme mp backup acidcamp "${CFG[@]}"
BK="$(find "$HOME/.mneme/backups/acidcamp" -name store.sqlite3 | head -1)"
[ -n "$BK" ] || fail "backup has no bindings"
find "$HOME/.mneme/backups/acidcamp" -name 'index.tvim' | grep -q . && fail "backup wrongly kept index.tvim"

echo "-- restore preserves bindings without re-embed --"
rm -rf "$STORE"
mneme mp restore acidcamp "${CFG[@]}"
[ -f "$STORE/turbovec/mempalace_drawers/store.sqlite3" ] || fail "restore did not bring bindings back"

# (The `mneme up` store-health gate is covered by tests/unit/test_mp_up_gate.py — it needs a
#  full CampaignGenerator component to reach, which is out of scope for a mempalace acid test.)
echo "PASS: 003 bring-up acid test ($EMBEDDER)"
