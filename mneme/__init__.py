"""mneme — the single-authority installer/orchestrator (the `mneme` CLI).

Named for Mneme, the Muse of memory (kin to the mempalace store). The name is also
deliberately *not* `platform`: a top-level package called `platform` shadows the Python
standard-library `platform` module on `sys.path` and breaks `import platform` (including
pytest's own startup), so `mneme` is both the better name and the safe one.
"""

__version__ = "0.1.0"
