# Contract — `mneme` CLI

The CLI is the manager's interface. Every command is **honest** (Principle I): a non-zero
exit code means the silicon did not confirm success. No command echoes declared state as if
it were observed.

Global: all commands read `mneme.yaml` from the repo root (override `--config PATH`).
`--json` emits machine-readable output. Validation failure (schema/integrity/cycle) →
exit 2 before any side effect.

---

## `mneme install`
Create/validate the venv, install every in-scope component at its pin in `order.install`,
then render every `DerivedConfig`.

- **Pre**: valid `mneme.yaml`; component sources resolvable.
- **Post**: venv exists; each component installed at exactly its `pin` (non-editable);
  each `config_target` written with a current source-sha256 stamp.
- **Exit**: `0` all installed + rendered & verified; `2` invalid config; `1` any component
  unresolved/failed (names the component; does **not** report success on partial result, FR-006).
- **Idempotent**: re-running with an unchanged `mneme.yaml` is a no-op (same pins, same hashes).

## `mneme apply`
Re-render all `DerivedConfig` from the current `mneme.yaml`; restart affected `managed`
services so none runs on a stale copy (FR-009).

- **Pre**: system installed.
- **Post**: every `config_target` regenerated with a current stamp; every `managed` service
  whose rendered inputs changed has been restarted; no component left on a prior value.
- **Exit**: `0` re-rendered (+ restarted) & verified; `1` a restart/health-check failed
  (names the service); `2` invalid config.
- **Note**: `apply` is the supported write-propagation path. (`install` also re-renders; `apply`
  is the lighter "config changed, code didn't" path.)

## `mneme up`
Start `managed` services in `order.startup`, health-checking each before starting dependents;
health-check (not start) any `managed: false` external dependency (e.g. the DGX endpoint).

- **Pre**: system installed.
- **Post**: all managed services running and reachable; external deps confirmed reachable.
- **Exit**: `0` all up & reachable; `1` a service failed to start or a dependency is
  unreachable (names it; never reports up on an unreachable result, FR-014); `2` invalid config.

## `mneme down`
Stop the `managed` services `mneme` started (reverse `order.startup`).

- **Post**: managed services stopped. External deps untouched.
- **Exit**: `0` stopped; `1` a stop failed (names it).

## `mneme status`
Report, per component, the **observed installed** version vs its `pin`; per service, live
reachability; and any `DerivedConfig` drift. Pure read — no side effects.

- **Output** (per row): component/service name · observed · expected · `PASS`/`FAIL` · note.
- **FAIL conditions** (Principle I): installed version ≠ pin; a service that should be up is
  unreachable; a `config_target` whose stamped source-sha256 ≠ current source.
- **Exit**: `0` only if **every** row is `PASS`; `1` if any `FAIL` (a red dashboard exits red).

---

## Cross-cutting contract guarantees
- **Observed-not-declared**: `status` never derives "installed version" from `mneme.yaml`.
- **No second authority**: no command writes a lockfile or a competing config store; the only
  writes are the venv, `DerivedConfig` targets, and the disposable run/PID bookkeeping.
- **Fail loud**: partial/unverified outcomes exit non-zero and name the unit (FR-006/014).
- **Single edit→propagate path**: changing config = edit `mneme.yaml` → `apply`/`install`;
  there is no command that mutates a `DerivedConfig` directly.
