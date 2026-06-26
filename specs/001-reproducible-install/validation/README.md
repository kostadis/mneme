# Validation harness — SC-005 reproducibility acid test

**Proof environment, NOT a deployment target.** It proves the tool is reproducibly installable and
its core loop works *from the authority alone*, in true isolation — a clean container has no
pre-existing `~/.venvs/main`, no `~/src` checkouts, and none of the host's operator discipline, so a
passing run can't be a configured-box illusion (see
[research D10](../research.md#d10--containerized-validation-harness-sc-005-acid-test)).

## Run

```bash
bash run-validation.sh                                              # on the host
docker compose run --rm validate                                   # clean container
```

## What it proves (reframed for the hypostasis/mneme split)

`run-validation.sh`, from a self-contained sample authority (no real components/substrate):

1. both commands resolve — `hypostasis` + `mneme` (the package installs cleanly);
2. `hypostasis status` runs and reports honestly;
3. `hypostasis apply` renders the wiring with a `# hypostasis-rendered` source-hash stamp;
4. change one value + apply → **no stale copy** (Principle V / SC-004);
5. `mneme up <campaign> --dry-run` previews the per-campaign launch incl. env-delivery.

Exit non-zero on any FAIL (Principle I — a red dashboard exits red).

## Scope (honest)

It does **not** install the heavy components or reach the real DGX/rpg-lib substrate — that needs
the DGX + the component repos (D2). This proves the **tool**, not a live system. Bringing the real
substrate up is hypostasis's still-open job ([#1](https://github.com/kostadis/mneme/issues/1)).
Containerizing the components *as the deployment model* is a deliberate future `002`, not this — do
not let this harness grow into that by momentum.
