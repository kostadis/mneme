"""Hermetic tests: no developer-shell mempalace env, no cross-test probe cache (GH #26),
and no inherited git repository context."""

from __future__ import annotations

import os

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


@pytest.fixture(autouse=True)
def _hermetic_git_env(monkeypatch):
    """Drop every inherited GIT_* var. Under `git rebase --exec` (or a hook) git exports
    GIT_DIR & co., and the tests' tmp-dir `git init`/commit/push would then act on the
    REAL repository — they once created branches in it and pushed one to origin."""
    for v in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(v)
