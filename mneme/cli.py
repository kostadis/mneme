"""The `mneme` CLI — spin up the campaign runtime for a specific campaign.

Run `hypostasis` once to configure the environment; run `mneme up <campaign>`
each time you want to work on a campaign.
"""

from __future__ import annotations

from pathlib import Path

import typer

from hypostasis import config as cfg
from hypostasis.models import ConfigEntity, MnemeIdentity

from . import lifecycle
from .mempalace import discover as _discover
from .mempalace import ownership as _ownership
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


def _resolve_campaign_dir(entity: ConfigEntity, campaign: str, campaign_dir: str | None) -> Path:
    """An explicit --dir wins; otherwise resolve the name across declared trees (005)."""
    if campaign_dir:
        cdir = Path(campaign_dir).expanduser()
        if not cdir.is_dir():
            raise _discover.DiscoveryError(f"campaign workspace not found: {cdir}")
        return cdir
    return _discover.find(entity, campaign).path


def _ensure_identity(entity: ConfigEntity, config: str) -> MnemeIdentity:
    """Return this mneme's identity, minting + reporting it on first need (005, FR-012)."""
    if entity.mneme_identity and entity.mneme_identity.id:
        return entity.mneme_identity
    identity = cfg.ensure_mneme_identity(config)
    typer.echo(f"minted mneme identity {identity.id}")
    return identity


@app.command()
def integrate(
    campaign: str = typer.Argument(..., help="Campaign name (resolved across declared trees)"),
    campaign_dir: str = typer.Option(
        None, "--dir", "-d", help="Explicit campaign workspace path (overrides the name lookup)"
    ),
    config: str = _config_opt,
) -> None:
    """Claim CAMPAIGN for this mneme — drop .mneme/owner.yaml only (no provisioning, 005)."""
    entity = _load_or_exit(config)
    try:
        cdir = _resolve_campaign_dir(entity, campaign, campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL integrate: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    identity = _ensure_identity(entity, config)
    try:
        owner = _ownership.integrate_campaign(cdir, identity)
    except _ownership.OwnershipError as e:
        typer.echo(f"FAIL integrate: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"integrated '{campaign}' (owner {owner.mneme_id}) → {_ownership.owner_path(cdir)}")


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
    """Bring CampaignGenerator up for CAMPAIGN (gate deps, render wiring, export env, start).

    Refuses a foreign-owned campaign and integrates an un-integrated one first (005, FR-017)."""
    entity = _load_or_exit(config)
    try:
        cdir = _resolve_campaign_dir(entity, campaign, campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL up: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None

    # Ownership gate (005). On dry-run, classify without minting/writing (no side effects).
    identity = entity.mneme_identity if dry_run else _ensure_identity(entity, config)
    state = _ownership.classify(cdir, identity)
    if state is _ownership.OwnerState.FOREIGN:
        owner = _ownership.read_owner(cdir)
        typer.echo(
            f"FAIL up: '{campaign}' is owned by a different mneme "
            f"({owner.mneme_id if owner else '?'}) — refusing", err=True,
        )
        raise typer.Exit(EXIT_RUNTIME) from None
    if not dry_run and state is _ownership.OwnerState.UNINTEGRATED:
        _ownership.integrate_campaign(cdir, identity)  # claim before provisioning

    try:
        result = lifecycle.up(
            entity, campaign, campaign_dir=str(cdir), session=session, port=port, dry_run=dry_run
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
