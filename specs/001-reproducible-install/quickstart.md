# Quickstart — Validate Reproducible Install & Unified Config

Runnable validation scenarios that prove the feature works end-to-end. Each maps to a
Success Criterion in [spec.md](./spec.md). Run from the repo root with the `hypostasis` CLI
installed in the target venv. See [contracts/cli.md](./contracts/cli.md) for command details.

## Prerequisites
- A throwaway/fresh venv path set in `hypostasis.yaml` `venv:`.
- `hypostasis.yaml` filled in for this environment (the only file you edit). See
  [contracts/hypostasis-yaml.schema.md](./contracts/hypostasis-yaml.schema.md).
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
  ~/src/CampaignGenerator ~/src/dgx ~/src/mempalace ~/src/mytools/rpg-lib
```
**Expect**: matches only in rendered config files / templates, **none** in component logic.

## Scenario 2 — Bring the system up in order (SC-006)
```
mneme up
```
**Expect**: exit 0; DGX endpoint health-checked first; managed services (`turbovecdb`,
`rpg_lib`) started in `order.startup` and each reachable before dependents. No manual
service-start steps used.
```
mneme down
```
**Expect**: managed services stopped; external DGX untouched.

## Scenario 3 — Honest status, including drift (SC-003)
```
mneme up && hypostasis status
```
**Expect**: exit 0; every component row shows observed version == pin (PASS); every service
reachable (PASS).
**Now force a lie** — stop a service out of band, then:
```
hypostasis status
```
**Expect**: exit 1; the stopped service row is `FAIL` (unreachable), not assumed up.
**Version drift** — install a different version of one component by hand, then `hypostasis status`
**Expect**: exit 1; that component row `FAIL` (installed ≠ pin).

## Scenario 4 — Change one value, everything follows, no stale copies (SC-004)
```
# edit hypostasis.yaml: change machines.dgx.endpoint to a new IP — ONE edit, one file
hypostasis apply
```
**Expect**: exit 0; every `DerivedConfig` referencing the DGX endpoint regenerated with a
fresh stamp; affected managed services restarted.
**Verify no stale copy**:
```
hypostasis status            # no render drift; all PASS
grep -rn "<old-ip>" <all config_targets>   # zero matches
```
**Expect**: nothing still references the old endpoint (SC-004 = 100% propagation, 0 stale).

## Scenario 5 — Reproducibility in a clean container (SC-005, **canonical acid test**)
A clean container is the most honest "fresh environment": no pre-existing venv, no `~/src`
checkouts, no operator-tweaked state. This is the canonical SC-005 proof and the home for the
full integration loop in true isolation. See [research D10](./research.md#d10--containerized-validation-harness-sc-005-acid-test)
and `validation/` (Dockerfile + compose + README). **The container is a proof environment, not
the install target** — containerizing the system as a deployment model would be a separate 002.

```
cd specs/001-reproducible-install/validation
docker compose build
docker compose run --rm validate     # runs install -> up -> status -> apply loop
```
**Expect**: inside the clean container, from `hypostasis.yaml` alone, the system installs at pins,
comes up on canonical ports (`8000`/`8077`, no host conflict — separate netns), and `status`
is all-PASS — with **zero** per-component edits.

**DGX sub-decision (test both ways)** — set in the compose env:
- *Real DGX reachable*: `mneme up` health-checks the real endpoint; change
  `machines.dgx.endpoint` and confirm it follows (doubles as SC-004).
- *DGX stubbed/unreachable*: confirm `hypostasis status` reports the real DGX **unreachable
  honestly** (exit 1, FAIL row) rather than wedging or showing a false green.

*(A second physical machine is an equivalent but higher-friction proof; the container gives the
same guarantee on demand.)*

## Failure-honesty checks (Principle I / FR-006, FR-014)
- Point a component `pin` at a non-existent ref → `hypostasis install` exits 1 and **names** it.
- Make a `managed` service's `start` command fail → `mneme up` exits 1 and names the service;
  it does not report the system up.
