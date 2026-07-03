# Quickstart — Validate Reproducible Install & Unified Config

Runnable validation scenarios that prove the feature works end-to-end. Each maps to a
Success Criterion in [spec.md](./spec.md). Run from the repo root with the `hypostasis` CLI
installed in the target venv. See [contracts/cli.md](./contracts/cli.md) for command details.

## Prerequisites
- A throwaway/fresh venv path set in `hypostasis.yaml` `venv:`.
- `hypostasis.yaml` filled in for this environment (the only file you edit; default path
  `~/.config/hypostasis/hypostasis.yaml`, XDG, override via `--config`/`-c` — never in this
  repo). See [contracts/hypostasis-yaml.schema.md](./contracts/hypostasis-yaml.schema.md).
- Component sources reachable at their declared `source` + `pin`.

## Scenario 1 — Reproducible install from one source of truth (SC-001, SC-002)
```
hypostasis install
```
**Expect**: exit 0; venv created; all six components installed at their pins; every
`config_target` written with a `source-sha256` stamp.
**Verify (SC-002)** — the hardcoded constants are gone from logic:
```
grep -rn "192.0.2.10\|5etools-kostadis/data\|localhost:8000\|8077\|.venvs/main" \
  ~/src/CampaignGenerator
```
**Expect**: matches only in rendered config files / templates, **none** in component logic.
(Per tasks.md T022: CampaignGenerator was the only repo where mneme externalized constants —
dgxlib/turbovecdb are install-only libraries, mempalace/rpg-lib are already env/CLI-driven,
gm-assistant is markdown; none of those needed constant removal.)

## Scenario 2 — Launch a campaign (SC-006)
```
mneme up <campaign>
```
**Expect**: exit 0; the DGX endpoint and rpg-lib (external substrate) health-checked, the
campaign's mempalace store health-checked, `hypostasis.yaml`'s `env:` exported, and that
campaign's CampaignGenerator instance started and reachable on its port (`--port`, default
`5000`). No manual service-start steps used. (`--dry-run` previews the plan and starts
nothing.)
```
mneme down <campaign>
```
**Expect**: that campaign's CampaignGenerator instance stopped; the substrate untouched.

## Scenario 3 — Honest status, including drift (SC-003)
```
hypostasis status
```
**Expect**: exit 0; every component row shows observed version == pin (PASS); every declared
service (`dgx`, `rpg_lib` — both external, health-checked only) reachable (PASS).
**Now force a lie** — stop a service out of band (or point `hypostasis.yaml` at an
unreachable endpoint), then:
```
hypostasis status
```
**Expect**: exit 1; the unreachable service row is `FAIL`, not assumed up.
**Version drift** — install a different version of one component by hand, then `hypostasis status`
**Expect**: exit 1; that component row `FAIL` (installed ≠ pin).

## Scenario 4 — Change one value, everything follows, no stale copies (SC-004)
```
# edit hypostasis.yaml: change machines.dgx.endpoint to a new IP — ONE edit, one file
hypostasis apply
```
**Expect**: exit 0; every `DerivedConfig` referencing the DGX endpoint regenerated with a
fresh stamp. There is no local managed service to restart (DGX/rpg-lib are external
substrate `hypostasis` never starts) — the guarantee is regenerate + fresh stamp, verified by
`status` showing no drift.
**Verify no stale copy**:
```
hypostasis status            # no render drift; all PASS
grep -rn "<old-ip>" <all config_targets>   # zero matches
```
**Expect**: nothing still references the old endpoint (SC-004 = 100% propagation, 0 stale).

## Scenario 5 — Reproducibility in a clean container (SC-005, **canonical acid test**)
A clean container is the most honest "fresh environment": no pre-existing venv, no `~/src`
checkouts, no operator-tweaked state. See [research D10](./research.md#d10--containerized-validation-harness-sc-005-acid-test)
and `validation/` (Dockerfile + compose + README). **The container is a proof environment, not
the install target** — containerizing the system as a deployment model would be a separate 002.

```
cd specs/001-reproducible-install/validation
bash run-validation.sh              # on the host
docker compose run --rm validate    # clean container
```
**Expect** (6 steps, from a self-contained sample authority — no real components/substrate):
1. both commands resolve (`hypostasis --help`, `mneme --help`);
2. a throwaway `hypostasis.yaml` is built pointing at a dummy DGX/rpg-lib and one component;
3. `hypostasis status` runs and reports honestly (FAILs on the dummy box are expected — the
   point is it ran and told the truth);
4. `hypostasis apply` renders the wiring with a `# hypostasis-rendered` source-hash stamp;
5. change one value + re-apply → the new value is rendered and **no stale copy** remains
   (SC-004);
6. `mneme up <campaign> --dry-run` previews the per-campaign launch, including env-delivery
   (`MEMPALACE_BACKEND`).

**Scope (honest)**: this proves the tool installs and its authority→render→status loop works
in isolation — it does **not** install the six real components or reach the real DGX/rpg-lib
substrate (that needs the DGX + the component repos; still open, see
[GitHub issue #1](https://github.com/kostadis/mneme/issues/1)). See `validation/README.md`
for the full scope statement.

*(A second physical machine is an equivalent but higher-friction proof; the container gives the
same guarantee on demand.)*

## Failure-honesty checks (Principle I / FR-006, FR-014)
- Point a component `pin` at a non-existent ref → `hypostasis install` exits 1 and **names** it.
- Make the campaign's CampaignGenerator `start` command fail → `mneme up <campaign>` exits 1
  and names it; it does not report the campaign up.
