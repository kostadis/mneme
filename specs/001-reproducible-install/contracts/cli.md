# Contract — `hypostasis` + `mneme` CLIs

*Reflects the shipped two-command split — `hypostasis` (environment config) and `mneme`
(per-campaign runtime). `mneme mp` (mempalace management) and `mneme integrate` (feature 005)
are summarized below; `README.md` is the source of truth for their full command lists.*

Each CLI is its manager's interface. Every command is **honest** (Principle I): a non-zero
exit code means the silicon did not confirm success. No command echoes declared state as if
it were observed.

Global: all commands read `hypostasis.yaml` from its default XDG path
(`~/.config/hypostasis/hypostasis.yaml`), overridable via `--config`/`-c PATH`. The file is
never committed to this repo. `--json` emits machine-readable output. Validation failure
(schema/integrity/cycle) → exit 2 before any side effect.

---

## `hypostasis install`
Create/validate the venv, install every in-scope component at its pin in `order.install`,
then render every `DerivedConfig`.

- **Pre**: valid `hypostasis.yaml`; component sources resolvable.
- **Post**: venv exists; each component installed at exactly its `pin` (non-editable);
  each `config_target` written with a current source-sha256 stamp.
- **Exit**: `0` all installed + rendered & verified; `2` invalid config; `1` any component
  unresolved/failed (names the component; does **not** report success on partial result, FR-006).
- **Idempotent**: re-running with an unchanged `hypostasis.yaml` is a no-op (same pins, same hashes).

## `hypostasis apply`
Re-render all `DerivedConfig` from the current `hypostasis.yaml`, stamping each with a fresh
source hash so no component runs on a stale copy (FR-009). There is no local managed service
for `apply` to restart — the DGX endpoint and rpg-lib are external substrate `hypostasis`
never starts; the per-campaign CampaignGenerator instance is `mneme`'s to start/stop.

- **Pre**: system installed.
- **Post**: every `config_target` regenerated with a current stamp; no component left on a
  prior value.
- **Exit**: `0` re-rendered & verified (no stale stamp remains); `1` a render/health-check
  failed (names it); `2` invalid config.
- **Note**: `apply` is the supported write-propagation path. (`install` also re-renders; `apply`
  is the lighter "config changed, code didn't" path.)

## `mneme up <campaign>`
Launch that campaign's CampaignGenerator instance on the environment `hypostasis` configured.
Resolves the campaign workspace under `data_roots.campaigns`; health-gates the shared
substrate (the `services` declared `managed: false` — DGX endpoint, rpg-lib — checked, never
started) and the campaign's mempalace store; exports `hypostasis.yaml`'s `env:` into the
process; starts CampaignGenerator scoped to that campaign on `--port` (default `5000`).

- **Pre**: environment installed (`hypostasis install`); campaign workspace exists.
- **Post**: that campaign's CampaignGenerator instance running and reachable on its port.
- **Options**: `--port`/`-p` (default `5000`); `--dry-run` (preview the plan, start nothing).
- **Exit**: `0` up & reachable; `1` a substrate/mempalace health gate failed or the process
  failed to start (names it; never reports up on an unreachable result, FR-014); `2` invalid
  config.
- **Note**: there is no cross-service managed-dependency startup order here — `mneme` never
  starts the DGX endpoint or rpg-lib (both are external substrate it only health-checks); the
  only process it starts/stops is this one campaign's CampaignGenerator instance. (Ownership
  gating and `mneme integrate` were added later, in feature 005 — see
  `specs/005-multi-root-campaigns/`.)

## `mneme down <campaign>`
Stop that campaign's CampaignGenerator instance (the one on `--port`).

- **Options**: `--port`/`-p` (default `5000`, must match the `up` that started it).
- **Post**: that campaign's instance stopped. Substrate (DGX/rpg-lib) untouched.
- **Exit**: `0` stopped; `1` a stop failed (names it).

## `hypostasis status`
Report, per component, the **observed installed** version vs its `pin`; per service, live
reachability; and any `DerivedConfig` drift. Pure read — no side effects.

- **Output** (per row): component/service name · observed · expected · `PASS`/`FAIL` · note.
- **FAIL conditions** (Principle I): installed version ≠ pin; a service that should be up is
  unreachable; a `config_target` whose stamped source-sha256 ≠ current source.
- **Exit**: `0` only if **every** row is `PASS`; `1` if any `FAIL` (a red dashboard exits red).

## `mneme mp`, `mneme integrate`
Out of scope for this contract — per-campaign mempalace management and multi-root campaign
ownership were added by features 002/003/005, after 001 shipped. `mneme mp` is a
14-subcommand group for per-campaign mempalace bring-up/backup/restore/regenerate/etc.; see
`README.md`'s `mneme mp` table for the current command list (source of truth) and
`specs/002-manage-campaign-mempalaces/` for its design. `mneme integrate` claims a campaign
(writes `.mneme/owner.yaml`, no provisioning) — see `specs/005-multi-root-campaigns/`.

---

## Cross-cutting contract guarantees
- **Observed-not-declared**: `status` never derives "installed version" from `hypostasis.yaml`.
- **No second authority**: no command writes a lockfile or a competing config store; the only
  writes are the venv and `DerivedConfig` targets. `mneme` keeps no separate PID/run
  directory of its own — for `mneme up`/`down`, PID tracking is delegated to whatever
  CampaignGenerator itself tracks for that port.
- **Fail loud**: partial/unverified outcomes exit non-zero and name the unit (FR-006/014).
- **Single edit→propagate path**: changing config = edit `hypostasis.yaml` → `apply`/`install`;
  there is no command that mutates a `DerivedConfig` directly.
