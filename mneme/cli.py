"""The `mneme` CLI — spin up the campaign runtime for a specific campaign.

Run `hypostasis` once to configure the environment; run `mneme up <campaign>`
each time you want to work on a campaign.
"""

from __future__ import annotations

import typer

from hypostasis import config as cfg
from hypostasis.models import ConfigEntity

from . import lifecycle
from .mempalace.cli import app as mp_app

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INVALID_CONFIG = 2

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Spin up the campaign runtime (CampaignGenerator) for a specific campaign.",
)

app.add_typer(mp_app, name="mp", help="Manage per-campaign mempalaces.")

_config_opt = typer.Option(
    str(cfg.default_config_path()), "--config", "-c", help="Path to hypostasis.yaml"
)


def _load_or_exit(config_path: str) -> ConfigEntity:
    try:
        return cfg.load(config_path)
    except FileNotFoundError:
        typer.echo(f"error: env config not found: {config_path}", err=True)
        typer.echo(
            "  copy hypostasis.example.yaml → "
            f"{cfg.default_config_path()} and edit it.", err=True,
        )
        raise typer.Exit(EXIT_INVALID_CONFIG) from None
    except cfg.ConfigError as e:
        typer.echo("error: invalid hypostasis.yaml:", err=True)
        for problem in e.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None


@app.command()
def up(
    campaign: str = typer.Argument(..., help="Campaign name (resolved under data_roots.campaigns)"),
    campaign_dir: str = typer.Option(
        None, "--dir", "-d", help="Explicit campaign workspace path (overrides the name lookup)"
    ),
    session: str = typer.Option(None, "--session", "-s", help="Session dir (rel/absolute)"),
    port: int = typer.Option(5000, "--port", "-p"),
    config: str = _config_opt,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan; start nothing"),
) -> None:
    """Bring CampaignGenerator up for CAMPAIGN (gate deps, render wiring, export env, start)."""
    entity = _load_or_exit(config)
    try:
        result = lifecycle.up(
            entity, campaign, campaign_dir=campaign_dir, session=session, port=port, dry_run=dry_run
        )
    except lifecycle.LifecycleError as e:
        typer.echo(f"FAIL up: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for line in result.report():
        typer.echo(line)


@app.command()
def down(
    campaign: str = typer.Argument(..., help="Campaign name"),
    port: int = typer.Option(5000, "--port", "-p"),
    config: str = _config_opt,
) -> None:
    """Stop CampaignGenerator for CAMPAIGN (the instance on --port)."""
    entity = _load_or_exit(config)
    try:
        lifecycle.down(entity, campaign, port=port)
    except lifecycle.LifecycleError as e:
        typer.echo(f"FAIL down: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"stopped CampaignGenerator for '{campaign}' (port {port})")


def main() -> None:  # pragma: no cover - thin entry shim
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
