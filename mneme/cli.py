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
from dataclasses import asdict

import typer

from . import config as cfg
from . import install as inst
from . import render as rnd
from . import status as sts
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
    """Re-render derived configs so nothing runs on a stale copy (Principle V)."""
    entity = _load_or_exit(config)

    try:
        written = [str(p) for p in rnd.render_and_write_all(entity)]
    except Exception as e:  # noqa: BLE001 - render failure must fail loud, named
        typer.echo(f"FAIL apply: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None

    # Verify no render drift remains (the re-render took).
    stale = [
        c for n in entity.order.install
        if (c := entity.components[n]).config_template
        and not sts.render_row(entity, c).ok
    ]
    # mneme runs no managed services (dgx, rpg_lib are external); any external dep
    # whose wiring changed must be restarted by its owner (hypostasis, issue #0005).
    externals = [n for n in entity.order.startup
                 if (s := entity.services.get(n)) is not None and not s.managed]

    if json:
        typer.echo(_json.dumps({
            "rerendered": written,
            "stale_after": [c.name for c in stale],
            "external_deps_to_check": externals,
        }))
    else:
        for path in written:
            typer.echo(f"re-rendered  {path}")
        if not written:
            typer.echo("(no derived configs to render)")
        typer.echo(
            "note: no managed services to restart — "
            f"external deps ({', '.join(externals) or 'none'}) are restarted by their "
            "owner (hypostasis) if their wiring changed."
        )
        if stale:
            typer.echo(f"FAIL: stale after apply: {[c.name for c in stale]}")
        else:
            typer.echo("OK: coherent")

    raise typer.Exit(EXIT_RUNTIME if stale else EXIT_OK)


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
    """Report observed component drift, reachability, and render drift (Principle I)."""
    entity = _load_or_exit(config)
    rows, code = sts.status_report(entity)
    if json:
        typer.echo(_json.dumps([asdict(r) for r in rows]))
    else:
        for r in rows:
            mark = "PASS" if r.ok else "FAIL"
            line = f"{mark}  {r.kind:9} {r.name:18} {r.observed:24} (pin {r.expected})"
            if r.note:
                line += f"  · {r.note}"
            typer.echo(line)
        passed = sum(1 for r in rows if r.ok)
        verdict = "OK" if code == EXIT_OK else "FAIL"
        typer.echo(f"\n{verdict}: {passed}/{len(rows)} checks passed")
    raise typer.Exit(code)


def main() -> None:  # pragma: no cover - thin entry shim
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
