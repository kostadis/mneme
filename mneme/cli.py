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
    """An explicit --dir wins; otherwise resolve the name across declared trees (005).

    Routed through ``_discover.resolve`` so both routes get the same ownership and
    alias-uniqueness gates (006, FR-016a/018) — `--dir` selects a workspace, it never
    confers ownership."""
    return _discover.resolve(entity, campaign, campaign_dir).path


class IdentityUndecided(Exception):
    """This host has no fleet identity and there is evidence to adopt — the operator must
    choose (006, FR-002/004/005). Carries the rendered remedies."""

    def __init__(self, lines: list[str]):
        self.lines = lines
        super().__init__("\n".join(lines))


def _discovered_campaign_dirs(entity: ConfigEntity) -> list[Path]:
    """Every discovered campaign dir, or [] if no trees are declared/reachable.

    Read-only, and never wedges the caller: an unconfigured or absent tree is not a reason
    to refuse an identity decision (Principle VI)."""
    try:
        return [r.path for r in _discover.discover(entity)]
    except _discover.DiscoveryError:
        return []


def resolve_identity(entity: ConfigEntity, config: str) -> MnemeIdentity:
    """Establish this host's fleet identity, adopting rather than re-minting (006, FR-002/003/004).

    Principle IV: a manager reconstructs itself from the objects it manages — "it adopts
    existing objects with their original identity and history, it does not re-mint them as
    new." A lazily minted uuid on a second host is exactly that re-mint, and it is why a
    shared checkout reads as foreign everywhere but the machine that claimed it.

    Adoption is never automatic (FR-005): choosing which fleet a campaign belongs to is an
    attribution decision, so mneme surfaces the evidence and stops."""
    if entity.mneme_identity and entity.mneme_identity.id:
        return entity.mneme_identity

    evidence = _ownership.owner_ids(_discovered_campaign_dirs(entity))
    if not evidence:  # greenfield — nothing to adopt (FR-003)
        identity = cfg.mint_mneme_identity(config)
        typer.echo(f"minted mneme identity {identity.id} (new fleet)")
        return identity

    lines = ["this host has no fleet identity."]
    if len(evidence) == 1:  # FR-002
        owner, camps = next(iter(evidence.items()))
        lines.append(
            f"the declared trees contain {len(camps)} campaign(s) owned by {owner} "
            f"({', '.join(camps)})."
        )
        lines.append(f"  join that fleet:  mneme identity adopt {owner}")
    else:  # FR-004 — more than one fleet present; never guess
        lines.append("the declared trees contain campaigns owned by several identities:")
        for owner, camps in evidence.items():
            lines.append(f"  {owner}  ({len(camps)}): {', '.join(camps)}")
        lines.append("  join one of them:  mneme identity adopt <id>")
    lines.append("  start a new one:  mneme identity mint")
    raise IdentityUndecided(lines)


def _ensure_identity(entity: ConfigEntity, config: str) -> MnemeIdentity:
    """Return this mneme's identity, establishing it on first need (005 FR-012, 006 FR-002)."""
    try:
        return resolve_identity(entity, config)
    except IdentityUndecided as e:
        for line in e.lines:
            typer.echo(f"  {line}" if line.startswith(" ") else line, err=True)
        raise typer.Exit(EXIT_RUNTIME) from None


identity_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Inspect, adopt, or mint this host's fleet identity (006).",
)
app.add_typer(identity_app, name="identity")


@identity_app.command("show")
def identity_show(config: str = _config_opt) -> None:
    """Report this host's fleet identity and where it came from — read-only (006, FR-006)."""
    entity = _load_or_exit(config)
    ident = entity.mneme_identity
    if ident and ident.id:
        typer.echo(f"identity: {ident.id}")
        if ident.label:
            typer.echo(f"label:    {ident.label}")
        typer.echo(f"source:   {config}")
        dirs = _discovered_campaign_dirs(entity)
        mine = _ownership.owner_ids(dirs).get(ident.id, [])
        typer.echo(
            f"campaigns owned here: {', '.join(mine) or 'none'} "
            f"({len(mine)} of {len(dirs)} discovered)"
        )
        raise typer.Exit(EXIT_OK)
    # Absence is a reportable state, not an error — but it must name the choice (Principle IX).
    typer.echo("identity: not established")
    evidence = _ownership.owner_ids(_discovered_campaign_dirs(entity))
    if not evidence:
        typer.echo("the declared trees contain no owned campaigns — nothing to adopt.")
        typer.echo("  start a fleet:  mneme identity mint")
    else:
        for owner, camps in evidence.items():
            typer.echo(
                f"the declared trees contain campaigns owned by {owner} ({', '.join(camps)})"
            )
        typer.echo(f"  join that fleet:  mneme identity adopt {next(iter(evidence))}")
        typer.echo("  start a new one:  mneme identity mint")
    raise typer.Exit(EXIT_OK)


@identity_app.command("adopt")
def identity_adopt(
    identity_id: str = typer.Argument(..., help="The fleet identity to join"),
    label: str = typer.Option(None, "--label", help="Optional human-readable label"),
    force: bool = typer.Option(
        False, "--force", help="Adopt even if this host's current identity owns campaigns"
    ),
    config: str = _config_opt,
) -> None:
    """Join an existing fleet — persist IDENTITY_ID as this host's identity (006, FR-001).

    Writes only hypostasis.yaml; never a campaign (FR-008)."""
    entity = _load_or_exit(config)
    current = entity.mneme_identity
    if current and current.id == identity_id.strip():
        typer.echo(f"identity already {current.id} — nothing to do")
        raise typer.Exit(EXIT_OK)
    if current and current.id and not force:
        # FR-007 — adopting would orphan whatever the current identity owns.
        owned = _ownership.owner_ids(_discovered_campaign_dirs(entity)).get(current.id, [])
        if owned:
            typer.echo(
                f"FAIL identity adopt: this host's identity {current.id} owns "
                f"{len(owned)} campaign(s) ({', '.join(owned)}) — adopting would orphan them. "
                "Re-run with --force to proceed.", err=True,
            )
            raise typer.Exit(EXIT_RUNTIME)
    try:
        adopted = cfg.adopt_mneme_identity(config, identity_id, label=label)
    except cfg.ConfigError as e:
        typer.echo("FAIL identity adopt:", err=True)
        for problem in e.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None
    typer.echo(f"adopted fleet identity {adopted.id} → {config}")
    now_mine = _ownership.owner_ids(_discovered_campaign_dirs(_load_or_exit(config))).get(
        adopted.id, []
    )
    typer.echo(f"now owns: {', '.join(now_mine) or 'no campaigns yet'}")


@identity_app.command("mint")
def identity_mint(
    label: str = typer.Option(None, "--label", help="Optional human-readable label"),
    config: str = _config_opt,
) -> None:
    """Start a NEW fleet — generate and persist a fresh identity (006, FR-003/006)."""
    entity = _load_or_exit(config)
    if entity.mneme_identity and entity.mneme_identity.id:
        typer.echo(
            f"FAIL identity mint: this host already has identity {entity.mneme_identity.id} "
            "— use `mneme identity adopt <id>` to change it", err=True,
        )
        raise typer.Exit(EXIT_RUNTIME)
    minted = cfg.mint_mneme_identity(config, label=label)
    typer.echo(f"minted fleet identity {minted.id} (new fleet) → {config}")


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

    # Ownership gate (005/006). On dry-run, classify without minting/writing (no side effects).
    identity = entity.mneme_identity if dry_run else _ensure_identity(entity, config)
    state = _ownership.classify(cdir, identity)
    if state is _ownership.OwnerState.FOREIGN:
        owner = _ownership.read_owner(cdir)
        owner_id = owner.mneme_id if owner else "?"
        mine = identity.id if identity and identity.id else "not established"
        typer.echo(
            f"FAIL up: campaign '{campaign}' is owned by {owner_id}; this mneme is {mine}. "
            f"If this host should join that fleet:  mneme identity adopt {owner_id}", err=True,
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
