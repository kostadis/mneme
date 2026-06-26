# 003 bring-up acid test (proof environment)

Proves `mneme mp bringup` works end-to-end against the **real** mempalace(kostadis-dev) +
turbovecdb — in two embedder lanes — against a **throwaway `$HOME/.mempalace`** (a fresh `mktemp`
store, deleted on exit), so it never touches the operator's live campaign stores. Mirrors
`specs/001-reproducible-install/validation/`.

## Run it

Direct `docker build` + `docker run` (no Compose plugin required):

```bash
# build the image (installs real mempalace + turbovecdb at the host-pinned commits + onnxruntime)
docker build -f specs/003-new-campaign-mempalace/validation/Dockerfile -t mneme-003-acid .

# lane 1 — local ONNX embedder (self-contained, no substrate/network)
docker run --rm -e EMBEDDER=onnx mneme-003-acid

# lane 2 — the real production LAN Qwen embedder (host networking; substrate must be reachable)
docker run --rm --network host \
  -e EMBEDDER=qwen \
  -e MEMPALACE_EMBEDDING_ENDPOINT=http://<embed-host>:<port> \
  -e MEMPALACE_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B \
  mneme-003-acid
```

Or, if you have the Compose plugin, `docker-compose.yml` defines the same two lanes as
`validate-onnx` / `validate-qwen`. On a host that already has mempalace installed you can also run
the script directly: `EMBEDDER=onnx bash specs/003-new-campaign-mempalace/validation/run-validation.sh`.

## What it asserts (exits non-zero on any FAIL — Principle I)

A real bring-up creates the dedicated turbovec store; `mempalace search` returns over the sample
docs; the cli-pointer (`palace:`) and global-alias faces are written; backup captures the bindings
and **excludes** `index.tvim`/`chroma.sqlite3`; and restore brings the bindings back **without
re-embedding**. (The `mneme up` store-health gate is covered by `tests/unit/test_mp_up_gate.py` — it
needs a full CampaignGenerator component to reach, out of scope for a mempalace acid test.)

The hermetic unit/integration suite (`pytest`, stub `mempalace`) is the bulk of coverage and needs
no container; this acid test is the real-silicon proof. The `qwen` lane is gated on the embedding
endpoint being reachable and fails honestly (exit 2) if it is not.

> Status: **validated** — both lanes pass against real mempalace + turbovecdb (ONNX self-contained,
> Qwen against the live LAN endpoint). The Dockerfile pins turbovecdb/mempalace to the exact commits
> the host runs (`hypostasis.yaml`'s declared versions); bump those refs as the pins move.
