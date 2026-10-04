"""Hermetic tests: no developer-shell mempalace env, no cross-test probe cache (GH #26)."""

from __future__ import annotations

import pytest

_VARS = (
    "MEMPALACE_BACKEND",
    "MEMPALACE_EMBEDDING_PROVIDER",
    "MEMPALACE_EMBEDDING_MODEL",
    "MEMPALACE_EMBEDDING_ENDPOINT",
    "MEMPALACE_EMBEDDING_API_KEY",
)


@pytest.fixture(autouse=True)
def _hermetic_mempalace_env(monkeypatch):
    from mneme.mempalace import embedder_guard

    for v in _VARS:
        monkeypatch.delenv(v, raising=False)
    embedder_guard._probe_cache.clear()
    # Never spawn a real mempalace probe from the suite; 384 = the stub store's dim.
    monkeypatch.setattr(embedder_guard, "default_prober", lambda entity: 384)
    yield
    embedder_guard._probe_cache.clear()
