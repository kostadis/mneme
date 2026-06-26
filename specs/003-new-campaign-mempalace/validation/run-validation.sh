#!/usr/bin/env bash
# 003 mempalace bring-up acid test (proof environment). Runs the REAL mempalace +
# turbovecdb bring-up against a throwaway $HOME/.mempalace, in EMBEDDER=onnx|qwen.
# Exits non-zero on any FAIL (Principle I: a red dashboard exits red). Runs in the
# container OR on the host. Proves the bring-up mechanics against real silicon.
set -euo pipefail

EMBEDDER="${EMBEDDER:-onnx}"
export HOME="$(mktemp -d)"          # throwaway store — never the operator's ~/.mempalace
export MEMPALACE_BACKEND=turbovec
ROOT="$(mktemp -d)/campaigns"
CAMP="$ROOT/acidcamp"
STORE="$HOME/.mempalace/palaces/acidcamp"

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
services: {}
components:
  mempalace: { source: { path: $HOME }, pin: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef }
order: { install: [mempalace], startup: [] }
data_roots: { campaigns: $ROOT }
YAML
MP="mneme mp --config $CONFIG"

fail() { echo "FAIL: $1"; exit 1; }

echo "-- bringup --"
$MP bringup acidcamp --no-backup
[ -f "$STORE/turbovec/mempalace_drawers/store.sqlite3" ] || fail "store not created"
grep -q '^palace: acidcamp' "$CAMP/mempalace.yaml" || fail "cli_pointer face missing palace:"
grep -q 'acidcamp' "$HOME/.mempalace/config.json" || fail "global alias not registered"

echo "-- search returns over the sample docs --"
mempalace search "vault" --palace "$STORE" | grep -qi vault || fail "search returned nothing"

echo "-- backup excludes rebuildable/legacy --"
$MP backup acidcamp
BK="$(find "$HOME/.mneme/backups/acidcamp" -name store.sqlite3 | head -1)"
[ -n "$BK" ] || fail "backup has no bindings"
find "$HOME/.mneme/backups/acidcamp" -name 'index.tvim' | grep -q . && fail "backup wrongly included index.tvim"

echo "-- restore preserves bindings without re-embed --"
rm -rf "$STORE"
$MP restore acidcamp
[ -f "$STORE/turbovec/mempalace_drawers/store.sqlite3" ] || fail "restore did not bring bindings back"

echo "-- mneme up gate: fails when the store is gone --"
rm -rf "$STORE"
if mneme up acidcamp --config "$CONFIG" --dry-run >/dev/null 2>&1; then : ; fi  # dry-run never gates
mneme up acidcamp --config "$CONFIG" >/dev/null 2>&1 && fail "mneme up should fail with no store" || true

echo "PASS: 003 bring-up acid test ($EMBEDDER)"
