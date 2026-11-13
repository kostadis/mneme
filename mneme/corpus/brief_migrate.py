"""One-shot, append-only addition of a `brief:` block to `.mneme/corpus.yaml` (feature 009, R11).

`plan` never writes; `apply` writes the previewed bytes atomically, and only if the file is still
the bytes the preview read. The file is never re-serialised: the original bytes stay an exact
prefix of the result, so the GM's comments and layout survive."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from mneme.corpus import config, resolve

DEFAULT_FILES = ("docs/planning.md",)


@dataclass(frozen=True)
class BriefFile:
    path: str
    kinds: tuple[str, ...]
    bytes: int


@dataclass(frozen=True)
class Plan:
    campaign_dir: Path
    original: bytes
    block: str
    new_bytes: bytes
    files: tuple[BriefFile, ...]
    total_bytes: int


@dataclass(frozen=True)
class Refusal:
    code: str
    detail: str
    findings: tuple = ()


class MigrationConflict(Exception):
    """corpus.yaml changed between the preview and the apply."""


def plan(campaign_dir: Path, recipe, files=DEFAULT_FILES) -> Plan | Refusal:
    campaign_dir = Path(campaign_dir)
    if not config.has_corpus(campaign_dir):
        return Refusal("not-declared", "this campaign has no .mneme/corpus.yaml")
    original = config.corpus_path(campaign_dir).read_bytes()
    try:
        cfg = config.parse(original, recipe, campaign_dir)
    except config.CorpusConfigError as e:
        return Refusal("invalid", str(e), e.findings)
    try:
        raw = yaml.safe_load(original) or {}
    except yaml.YAMLError as e:  # parse() already passed; defensive
        return Refusal("invalid", f"YAML parse error: {e}")
    if isinstance(raw, dict) and "brief" in raw:
        return Refusal("brief-exists", "corpus.yaml already has a `brief:` key; edit it by hand")
    res = resolve.resolve(cfg, campaign_dir, recipe)
    if not res.valid:
        return Refusal("invalid", "the corpus does not resolve cleanly", tuple(res.findings))

    norm: list[str] = []
    bad: list[str] = []
    for f in files:
        n, why = config._norm(f)
        if n is None:
            bad.append(f"{f}: {why}")
        elif n in norm:
            bad.append(f"{n}: listed twice")
        else:
            norm.append(n)
    if bad:
        return Refusal("invalid", "; ".join(bad))
    if not norm:
        return Refusal("invalid", "no brief files given")

    unavailable: list[str] = []
    undeclared: list[str] = []
    kinds_of: dict[str, tuple[str, ...]] = {}
    for n in norm:
        standing, kinds = resolve.brief_standing(cfg, res, campaign_dir, n)
        kinds_of[n] = kinds
        if standing == resolve.STANDING_ABSENT:
            unavailable.append(n)
        elif standing == resolve.STANDING_UNDECLARED:
            undeclared.append(n)
    if unavailable:
        return Refusal("brief-unavailable",
                       "declared but not on disk here: " + ", ".join(unavailable))
    if undeclared:
        return Refusal("brief-undeclared",
                       "not a file of any declared kind: " + ", ".join(undeclared))

    block = "brief:\n" + "".join(f"  - {p}\n" for p in norm)
    sep = b"" if (not original or original.endswith(b"\n")) else b"\n"
    new_bytes = original + sep + b"\n" + block.encode()
    try:
        cfg2 = config.parse(new_bytes, recipe, campaign_dir)
    except config.CorpusConfigError as e:
        return Refusal("invalid", str(e), e.findings)
    res2 = resolve.resolve(cfg2, campaign_dir, recipe)
    if not res2.valid or cfg2.brief != tuple(norm):
        return Refusal("invalid", "the edited corpus.yaml would not validate",
                       tuple(res2.findings))

    bf = tuple(BriefFile(n, kinds_of[n], os.stat(campaign_dir / n).st_size) for n in norm)
    return Plan(campaign_dir, original, block, new_bytes, bf, sum(b.bytes for b in bf))


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.chmod(tmp, path.stat().st_mode & 0o7777)  # mkstemp is 0600; keep the file's mode
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def apply(p: Plan) -> Path:
    path = config.corpus_path(p.campaign_dir)
    if not path.is_file() or path.read_bytes() != p.original:
        raise MigrationConflict("corpus.yaml changed since the preview; run the preview again")
    _write_atomic(path, p.new_bytes)
    return path
