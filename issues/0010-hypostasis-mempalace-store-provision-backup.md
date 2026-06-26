# 0010 — hypostasis should provision and back up the per-campaign mempalace data store

**Status:** open (filed 2026-06-26)
**Area:** hypostasis · data management · mempalace · backup/restore
**Related:** `specs/002-manage-campaign-mempalaces/` (mneme owns the *config*),
[[0006-campaign-creation-must-bootstrap-mempalace]] (config at creation), `MEMPALACE_HOWTO.md`
(shared-DB gotcha), constitution Principles III, IV, V

## The layering this issue addresses

Feature 002 / `mneme mp` manage the per-campaign mempalace **config** (the `.mneme/mempalace.yaml`
authority) and **orchestrate mining**. Nothing yet owns the **data store** lifecycle: provisioning
the index store for a campaign, and **backing it up / restoring it**. That is hypostasis's plane
(it already installs `mempalace` + `turbovecdb`); this issue is about the *data*, not the config.

```
  campaign docs + .mneme authority   ← authoritative inputs, already in the campaigns git repo (backed up)
            │ mine (mneme mp refresh)
            ▼
  mempalace index store (~/.mempalace, turbovec/chroma)   ← DERIVED; expensive to regenerate; not yet provisioned/backed-up by anyone
```

## What we want

hypostasis should:
1. **provision** a campaign's mempalace store at setup (or confirm the shared store exists and is
   healthy — `mempalace` already has `status`/`repair`), and
2. provide **backup / restore / snapshot** of the index data, at **per-campaign** granularity.

## Doctrine framing (important — keep the index non-authoritative)

- The index is a **derived cache** of (docs + authority + recipe). It is **not** a second authority
  (Principle V). A backup is a **cost optimization** (avoid recomputing LLM embeddings over
  thousands of lines) and a recovery aid (corruption), **never** a source of truth.
- The **authoritative** inputs are already backed up — they live in the campaigns git repo. So this
  issue is strictly about the **derived** store.
- Principle IV / Brick Test: the ground truth for the index is always *re-mine*. Restore-from-backup
  must therefore carry a **freshness check** (does the restored index match the current
  docs+authority+recipe?); on mismatch, re-mine rather than trust a stale restore (Principle I — a
  restored-but-stale index is exactly the False Green this doctrine kills). Restore is a fast-path,
  not an authority.

## Open questions

- **Shared-store granularity.** Campaigns share one `~/.mempalace/palace` with wings namespaced
  (HOWTO gotcha). Per-campaign backup of a shared store needs per-wing/namespace export
  (`mempalace` has `exporter.py` — does it support per-wing export/import cleanly?). Alternative:
  one store per campaign (cleaner isolation, more setup).
- **Trigger.** Manual (`hypostasis backup <campaign>`), scheduled, and/or automatic **before a
  destructive op** (re-mine / `mempalace repair`).
- **Where backups live.** Not in the campaigns repo (large derived blobs); a dedicated backup
  location / object store, clearly labeled non-authoritative and disposable.
- **Restore vs re-mine policy.** Default to re-mine as truth; offer restore + freshness-check as the
  fast path. Surface which one ran (observability — cf. [[0008-constitution-observability-gap]]).
- **Relation to 0006.** 0006 ensures the *config* exists at campaign creation; this ensures the
  *store* is provisioned and protected. Sequencing: create campaign → bootstrap config (0006) →
  provision store + first mine → backup (this issue).

## Why it matters

Re-mining a large campaign is slow and burns local-GPU/embedding time; losing the store to
corruption with no backup means a long, expensive rebuild. Owning provisioning + backup turns the
index into a managed, recoverable asset — while the doctrine keeps it honestly *derived*, never a
second truth to fall out of sync.
