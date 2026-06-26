# 003 bring-up acid test (proof environment)

Proves `mneme mp bringup` works end-to-end against the **real** mempalace(kostadis-dev) +
turbovecdb — in two embedder lanes — against a **throwaway `$HOME/.mempalace`**, so it never
touches the operator's live campaign stores. Mirrors `specs/001-reproducible-install/validation/`.

```bash
# without the substrate (self-contained, CI-able): local ONNX embedder
docker compose -f specs/003-new-campaign-mempalace/validation/docker-compose.yml run --rm validate-onnx

# with the substrate: the real production LAN Qwen embedder (gated on reachability)
MEMPALACE_EMBEDDING_ENDPOINT=http://<embed-host>:<port> \
  docker compose -f specs/003-new-campaign-mempalace/validation/docker-compose.yml run --rm validate-qwen

# or on the host directly:
EMBEDDER=onnx bash specs/003-new-campaign-mempalace/validation/run-validation.sh
```

What it asserts (exits non-zero on any FAIL — Principle I): a real bring-up creates the dedicated
turbovec store; search returns over the sample docs; the cli-pointer + global-alias faces are
written; backup captures the bindings and **excludes** `index.tvim`/`chroma.sqlite3`; restore brings
the bindings back **without re-embedding**; and `mneme up` **fails** when the store is gone.

The hermetic unit/integration suite (`pytest`, stub `mempalace`) is the bulk of coverage and needs
no container; this acid test is the real-silicon proof. The `qwen` lane needs the embedding endpoint
reachable and is skipped honestly if not.

> Status: authored alongside the feature; the container run requires the real mempalace/turbovecdb
> installs (and, for the `qwen` lane, the Spark endpoint) and is run on a host that has them.
