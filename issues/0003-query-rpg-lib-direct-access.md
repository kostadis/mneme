# 0003 — query_rpg_lib reaches into the rpg-lib index directly (should be HTTP-only)

**Status:** open (2026-06-24)
**Area:** CampaignGenerator · rpg-lib boundary · T019
**Related:** [[0002-cg-remaining-external-constants]], `query_rpg_lib.py`, `rpg_retriever.py`

## Problem

rpg-lib is an **external index service** — an index over a large file set, exposed via
`library_server` (HTTP, `:8000`). hypostasis/CG **interact with it but don't own it**. All access
should go through its HTTP API.

`CampaignGenerator/query_rpg_lib.py` violates this: it `from library_api import db` and opens
`rpg_library.db` **directly** (SQLite), bypassing the service. It is the **only** direct-access
site — `rpg_retriever.py` already speaks HTTP (`urllib`, URL from wiring).

T016 removed query_rpg_lib's `sys.path` hack and pointed it at the installed `library_api`, but
that only swapped one form of direct access for another. The real boundary fix is **HTTP**.

## Consequence (applied in hypostasis now)

Because direct access is the *only* reason anything in hypostasis's component set imports
`library_api` (and `claudelib` is only used by rpg-lib + pdf-translators, neither a hypostasis
component), hypostasis should **not install rpg-lib or claudelib**:
- `services.rpg_lib` → `managed: false` (health-checked external dependency, like the DGX; not
  started by hypostasis).
- rpg-lib and claudelib **removed from `components` / `order.install`**.

Until this bug is fixed, **`query_rpg_lib` is non-functional** (hypostasis no longer installs
`library_api` into the venv). That is the intended, tracked state.

## Fix

Rework `query_rpg_lib` to call rpg-lib's HTTP API (the search/get-book endpoints `library_server`
exposes) instead of importing `library_api`. If the HTTP API doesn't expose the needed queries,
either add them to rpg-lib (its concern) or retire `query_rpg_lib` and fold its refs.yaml-emit
into the HTTP path used by `rpg_retriever`.
