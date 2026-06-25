"""The `mneme` CLI — honest, single-authority manager.

Exit codes (contracts/cli.md):
  0  success, verified against silicon
  1  runtime FAIL (named; partial/unverified outcomes exit non-zero — Principle I)
  2  invalid mneme.yaml (before any side effect)

`install` is implemented here; `apply` / `up` / `down` / `status` are stubbed in
this phase (they arrive in later tasks) but still validate the authority so an
invalid config fails the same way everywhere.
"""

from __future__ import annotations

import json as _json

import typer

from . import config as cfg
from . import install as inst
from . import render as rnd
from .models import ConfigEntity

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INVALID_CONFIG = 2

DEFAULT_CONFIG = "mneme.yaml"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Single-authority installer/orchestrator for the campaign/DGX system.",
)

_config_opt = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Path to mneme.yaml")
_json_opt = typer.Option(False, "--json", help="Machine-readable output")


def _load_or_exit(config_path: str) -> ConfigEntity:
    try:
        return cfg.load(config_path)
    except FileNotFoundError:
        typer.echo(f"error: config not found: {config_path}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None
    except cfg.ConfigError as e:
        typer.echo("error: invalid mneme.yaml:", err=True)
        for problem in e.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None


@app.command()
def install(config: str = _config_opt, json: bool = _json_opt) -> None:
    """Install all components at their pins (order.install) and render derived configs."""
    entity = _load_or_exit(config)

    try:
        installed = inst.install_all(entity)
    except inst.InstallError as e:
        typer.echo(f"FAIL install: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None

    rendered: list[str] = []
    try:
        for derived in rnd.render_all(entity):
            rnd.write_rendered(derived)
            rendered.append(str(derived.target))
    except Exception as e:  # noqa: BLE001 - render failure must fail loud, named
        typer.echo(f"FAIL render: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None

    if json:
        typer.echo(_json.dumps({"installed": installed, "rendered": rendered}))
    else:
        typer.echo(
            f"OK: installed {len(installed)} components "
            f"({', '.join(installed)}); rendered {len(rendered)} configs"
        )


def _not_yet(command: str, task: str) -> None:
    """Validate the authority, then report this command is not in this phase yet."""
    typer.echo(
        f"'{command}' is not implemented in this phase (arrives in {task}).", err=True
    )
    raise typer.Exit(EXIT_RUNTIME)


@app.command()
def apply(config: str = _config_opt, json: bool = _json_opt) -> None:
    """Re-render derived configs and restart affected managed services (FR-009)."""
    _load_or_exit(config)
    _not_yet("apply", "T031")


@app.command()
def up(config: str = _config_opt, json: bool = _json_opt) -> None:
    """Start managed services in dependency order; health-check external deps."""
    _load_or_exit(config)
    _not_yet("up", "T028/T029")


@app.command()
def down(config: str = _config_opt, json: bool = _json_opt) -> None:
    """Stop the managed services mneme started (reverse order)."""
    _load_or_exit(config)
    _not_yet("down", "T028/T029")


@app.command()
def status(config: str = _config_opt, json: bool = _json_opt) -> None:
    """Report observed installed versions, reachability, and render drift."""
    _load_or_exit(config)
    _not_yet("status", "T025/T026")


def main() -> None:  # pragma: no cover - thin entry shim
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
