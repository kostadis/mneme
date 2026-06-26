"""Manage per-campaign mempalaces — the manager half of `mneme mp`.

`mneme mp` discovers campaigns, renders each campaign's derived mempalace config
from its single authority (`.mneme/mempalace.yaml`), reports honest observed
conformance, refreshes indexes by orchestrating the `mempalace` CLI, and publishes
recipe upgrades through a private working copy (never the active checkout).

The authority and the recorded dispositions live in the campaign, not here
(Principle III/IV); the recipe is the one mneme-owned shared artifact (FR-015).
"""
