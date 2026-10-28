"""Resolve a declared corpus against the disk and git (feature 007, data-model § ResolvedCorpus).

`config.py` says what the GM declared; this says what that declaration is on THIS checkout:
which files exist, which are minable, which are merely not checked out here (sparse, R7),
which are symlinks and where they really point (R5), which are gitignored (a named path is a
finding; a file only found by walking a dir is dropped, #64), and which kind
mines each file (R2). Nothing is assumed fine: a path that cannot be classified is a
finding or is reported in ``git`` rather than silently passed.
"""

from __future__ import annotations

import bisect
import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from mneme.mempalace.models import Recipe

from .config import CorpusConfig, Finding, shared_file_findings

# Extensions mempalace reads, mirrored from `READABLE_EXTENSIONS` (+ `PHP_EXTENSIONS`) and
# `SKIP_FILENAMES` in mempalace/miner.py:109-195. A file outside this set is listed with
# `minable: false`, so it is never reported as unmined (spec edge case, GH #31).
READABLE_EXTENSIONS = frozenset({
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".jsonl", ".yaml", ".yml",
    ".html", ".css", ".java", ".go", ".rs", ".swift", ".kt", ".kts", ".rb", ".sh", ".csv",
    ".sql", ".toml", ".tex", ".bib", ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".inl",
    ".cs", ".csproj", ".sln", ".razor", ".cshtml",
    ".php", ".php3", ".php4", ".php5", ".php7", ".php8", ".phtml", ".phps", ".phpt", ".inc",
    ".aw", ".fcgi", ".ctp", ".module", ".install", ".profile", ".theme", ".engine", ".twig",
    ".blade", ".tpl", ".latte", ".volt",
})
SKIP_FILENAMES = frozenset({
    "entities.json", "mempalace.yaml", "mempalace.yml", "mempal.yaml", "mempal.yml",
    ".gitignore", ".mempalaceignore", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
})

GIT_WORK_TREE = "work-tree"
GIT_NOT_A_WORK_TREE = "not-a-work-tree"  # nothing is skip-worktree or gitignored (reported)
GIT_UNAVAILABLE = "git-unavailable"  # git could not be run at all (reported)


@dataclass(frozen=True)
class ResolvedFile:
    """One file a kind resolves to. ``path`` is the declared path (what consumers open);
    ``target`` is the resolved campaign-relative file, set only when it differs (a symlink).
    ``mined_as`` is the kind whose wing holds the drawers (None: not mined / unresolved)."""

    path: str
    sha256: str
    minable: bool
    mined_as: str | None
    target: str | None = None

    @property
    def mined_path(self) -> str:
        """The file actually handed to the miner (mempalace opens with O_NOFOLLOW)."""
        return self.target or self.path


@dataclass(frozen=True)
class ResolvedKind:
    name: str
    standard: bool
    trust: str
    files: tuple[ResolvedFile, ...] = ()
    not_materialized: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedCorpus:
    campaign: str
    kinds: dict[str, ResolvedKind]
    findings: tuple[Finding, ...] = ()
    git: str = GIT_WORK_TREE  # GIT_* above: how far sparse/gitignore answers can be trusted

    @property
    def valid(self) -> bool:
        return not self.findings

    def mine_targets(self, kind: str) -> list[str]:
        """Distinct minable campaign-relative files the miner is handed for ``kind``: the
        resolved targets of every file whose mining kind is ``kind`` (R2)."""
        k = self.kinds.get(kind)
        if k is None:
            return []
        return sorted({f.mined_path for f in k.files if f.minable and f.mined_as == kind})


@dataclass
class _Git:
    state: str = GIT_UNAVAILABLE
    status: dict[str, str] = field(default_factory=dict)  # tracked relpath -> ls-files tag
    cwd: Path | None = None
    _keys: list[str] = field(default_factory=list, repr=False)
    _keys_n: int = field(default=-1, repr=False)

    def skip_worktree(self, rel: str) -> bool:
        return self.status.get(rel, "")[:1].upper() == "S"

    def tracked_under(self, rel: str) -> list[str]:
        if self._keys_n != len(self.status):  # sorted once; bisect per call
            self._keys = sorted(self.status)
            self._keys_n = len(self.status)
        pre = rel + "/"
        out = [rel] if rel in self.status else []
        i = bisect.bisect_left(self._keys, pre)
        while i < len(self._keys) and self._keys[i].startswith(pre):
            out.append(self._keys[i])
            i += 1
        return out

    def ignored(self, rels: list[str]) -> tuple[set[str], dict[str, str]]:
        """``(paths git ignores, {path: why} for paths it would not answer)``. ``--no-index``:
        a TRACKED file that matches an ignore rule still counts, since mempalace's matcher
        skips it too. One refused pathspec aborts git's whole batch (#82), so a failed batch
        is re-asked path by path and only the refused paths go unanswered. Raises
        ``GitIgnoreError`` when git cannot be run at all."""
        if self.state != GIT_WORK_TREE or not rels:
            return set(), {}
        out = self._check_ignore(rels)
        if out.returncode in (0, 1):  # 1 = none ignored
            return {p for p in out.stdout.split("\0") if p}, {}
        ignored: set[str] = set()
        refused: dict[str, str] = {}
        for rel in rels:
            one = self._check_ignore([rel])
            if one.returncode == 0:
                ignored.add(rel)
            elif one.returncode != 1:
                refused[rel] = one.stderr.strip() or f"git check-ignore exited {one.returncode}"
        return ignored, refused

    def _check_ignore(self, rels: list[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", "check-ignore", "--no-index", "-z", "--stdin"],
                cwd=self.cwd, env=_git_env(), input="\0".join(rels) + "\0",
                capture_output=True, text=True,
            )
        except OSError as e:
            raise GitIgnoreError(str(e)) from e


class GitIgnoreError(Exception):
    """``git check-ignore`` could not be run; gitignore filtering did not happen."""


def _git_env() -> dict[str, str]:
    # An inherited GIT_DIR / GIT_WORK_TREE would make git answer for another repository.
    return {k: v for k, v in os.environ.items()
            if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}


def _open_git(campaign_dir: Path) -> _Git:
    g = _Git(cwd=campaign_dir)
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=campaign_dir, env=_git_env(), capture_output=True, text=True,
        )
    except OSError:
        return g
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        g.state = GIT_NOT_A_WORK_TREE
        return g
    try:  # cwd-relative: only the campaign's own entries, even in a subdirectory campaign
        ls = subprocess.run(
            ["git", "ls-files", "-t", "-z"],
            cwd=campaign_dir, env=_git_env(), capture_output=True, text=True,
        )
    except OSError:
        return g
    if ls.returncode != 0:
        return g
    for rec in ls.stdout.split("\0"):
        if len(rec) > 2:
            g.status[rec[2:]] = rec[0]
    g.state = GIT_WORK_TREE
    return g


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_minable(rel: str) -> bool:
    name = os.path.basename(rel)
    return name not in SKIP_FILENAMES and os.path.splitext(name)[1].lower() in READABLE_EXTENSIONS


@dataclass
class _Entry:
    kind: str
    path: str
    target: str | None
    sha256: str
    minable: bool

    @property
    def key(self) -> str:  # the identity mempalace dedups on: the resolved file
        return self.target or self.path


class _Walker:
    """Classifies declared paths of ONE kind into entries / not_materialized / missing."""

    def __init__(self, campaign_dir: Path, git: _Git, findings: list[Finding]):
        self.root = campaign_dir
        self.real_root = os.path.realpath(campaign_dir)
        self.git = git
        self.findings = findings
        self._beneath: dict[str, bool] = {}

    def _inside(self, real: str) -> bool:
        return real == self.real_root or real.startswith(self.real_root + os.sep)

    def beneath_link(self, rel: str) -> bool:
        """Whether a parent directory of ``rel`` is a symlink. git refuses such a pathspec;
        the walker already carries the file's real path as its ``target``."""
        parent = os.path.dirname(rel)
        if not parent:
            return False
        if parent not in self._beneath:
            real = os.path.realpath(self.root / parent)
            self._beneath[parent] = real != os.path.join(self.real_root, parent)
        return self._beneath[parent]

    def _rel_real(self, real: str) -> str:
        return os.path.relpath(real, self.real_root).replace(os.sep, "/")

    def file_entry(self, kind: str, rel: str, entries: list[_Entry]) -> None:
        """Classify one path known to exist (lexically) as a file or a link to one."""
        full = self.root / rel
        real = os.path.realpath(full)
        is_link = real != os.path.join(self.real_root, rel)
        if not self._inside(real):
            self.findings.append(
                Finding("symlink-outside", f"resolves outside the campaign: {real}", path=rel)
            )
            return
        if not os.path.isfile(real):
            code = "symlink-not-file" if is_link else "not-a-file"
            why = "dangling" if not os.path.lexists(real) else "not a regular file"
            self.findings.append(Finding(code, f"{why}: resolves to {real}", path=rel))
            return
        target = self._rel_real(real) if is_link else None
        entries.append(_Entry(kind, rel, target, _sha256(Path(real)), _is_minable(target or rel)))

    def _sparse_link(self, rel: str, want: str) -> list[str]:
        """The would-be corpus paths of a dangling symlink whose target is outside this host's
        sparse cone (R7), not a broken link. ``want`` is the declared kind: ``"file"`` (target
        is a skip-worktree file -> ``[rel]``), ``"dir"`` (target is a directory whose tracked
        entries are all skip-worktree -> ``rel/<sub>`` each) or ``"any"`` (inside a dir walk,
        where a link may be either). A kind mismatch is not sparse: validity must not depend
        on the host. Empty when the link is not such a link."""
        full = self.root / rel
        if not (os.path.islink(full) and not os.path.exists(full)):
            return []
        real = os.path.realpath(full)
        if not self._inside(real):
            return []
        target = self._rel_real(real)
        tracked = self.git.tracked_under(target)
        if not tracked or not all(self.git.skip_worktree(p) for p in tracked):
            return []
        if target in tracked:
            return [rel] if want != "dir" else []
        return [rel + p[len(target):] for p in tracked] if want != "file" else []

    def _sparse_under(self, rel: str, real: str, nm: set[str]) -> None:
        """A LIVE directory link: skip-worktree entries under its real target are not
        materialized (R7), recorded link-relative like a dangling link's."""
        target = self._rel_real(real)
        for p in self.git.tracked_under(target):
            sub = rel + p[len(target):]
            if self.git.skip_worktree(p) and not os.path.lexists(self.root / sub):
                nm.add(sub)

    def declared_file(self, kind: str, rel: str, ents: list[_Entry], nm: set[str], miss: set[str]):
        full = self.root / rel
        if os.path.lexists(full):
            if os.path.isdir(full) and not os.path.islink(full):
                self.findings.append(Finding("not-a-file", "declared under `files` but is a "
                                             "directory (use `dirs`)", path=rel))
                return
            if sparse := self._sparse_link(rel, "file"):
                nm.update(sparse)  # target is outside this host's sparse cone
                return
            self.file_entry(kind, rel, ents)
            return
        self._absent(rel, nm, miss)

    def _absent(self, rel: str, nm: set[str], miss: set[str]) -> None:
        """A declared path not on disk: sparse (R7) or missing."""
        tracked = self.git.tracked_under(rel)
        if not tracked:
            miss.add(rel)  # not tracked, or no git to say otherwise
            return
        for p in tracked:
            (nm if self.git.skip_worktree(p) else miss).add(p)

    def declared_dir(self, kind: str, rel: str, ents: list[_Entry], nm: set[str], miss: set[str]):
        full = self.root / rel
        if not os.path.lexists(full):
            self._absent(rel, nm, miss)
            return
        if sparse := self._sparse_link(rel, "dir"):  # link to a dir outside the sparse cone
            nm.update(sparse)
            return
        real = os.path.realpath(full)
        if not self._inside(real):
            self.findings.append(
                Finding("symlink-outside", f"resolves outside the campaign: {real}", path=rel)
            )
            return
        if not os.path.isdir(real):
            self.findings.append(Finding("not-a-directory", "declared under `dirs` but "
                                         "is not a directory", path=rel))
            return
        if real != os.path.join(self.real_root, rel):  # declared dir is (under) a live link
            self._sparse_under(rel, real, nm)
        self._walk(kind, rel, {real}, ents, nm)
        for p in self.git.tracked_under(rel):  # partially sparse folder
            if self.git.skip_worktree(p) and not os.path.lexists(self.root / p):
                nm.add(p)

    def _walk(
        self, kind: str, rel: str, ancestors: set[str], ents: list[_Entry], nm: set[str]
    ) -> None:
        try:
            names = sorted(os.listdir(self.root / rel))
        except OSError as e:
            self.findings.append(Finding("unreadable", f"cannot list directory: {e}", path=rel))
            return
        for name in names:
            if name == ".git":
                continue
            child = f"{rel}/{name}"
            full = self.root / child
            if os.path.isdir(full):  # follows symlinked directories
                real = os.path.realpath(full)
                if not self._inside(real):
                    self.findings.append(Finding("symlink-outside",
                                                 f"resolves outside the campaign: {real}",
                                                 path=child))
                elif real not in ancestors:  # a link back to a parent would never end
                    if os.path.islink(full):
                        self._sparse_under(child, real, nm)
                    self._walk(kind, child, ancestors | {real}, ents, nm)
            elif sparse := self._sparse_link(child, "any"):
                nm.update(sparse)
            else:
                self.file_entry(kind, child, ents)


def resolve(cfg: CorpusConfig, campaign_dir: Path, recipe: Recipe) -> ResolvedCorpus:
    """Resolve every declared kind on this checkout. Never raises on a bad declaration:
    problems are ``findings``. ``recipe`` is accepted for symmetry with `config.load` (the
    standard kinds are already resolved into ``cfg``)."""
    campaign_dir = Path(campaign_dir)
    git = _open_git(campaign_dir)
    findings: list[Finding] = []
    walker = _Walker(campaign_dir, git, findings)

    per_kind: dict[str, tuple[list[_Entry], set[str], set[str]]] = {}
    for name, decl in cfg.kinds.items():
        ents: list[_Entry] = []
        nm: set[str] = set()
        miss: set[str] = set()
        for d in decl.dirs:
            walker.declared_dir(name, d, ents, nm, miss)
        for f in decl.files:
            walker.declared_file(name, f, ents, nm, miss)
        per_kind[name] = (ents, nm, miss)

    # Rule 4: one batched check-ignore. A path NAMED in corpus.yaml (a `files` entry of any
    # kind, a declared dir) that git ignores is a finding, and so is the ignored target of a
    # symlink that stays in the corpus. A file merely FOUND by walking a declared dir that git
    # ignores is not in the corpus: dropped silently, before rule 6 sees it ("if it's not
    # worth putting in git, it's not worth remembering", GM, mneme#64).
    named = {p for decl in cfg.kinds.values() for p in decl.dirs + decl.files}
    named_files = {p for decl in cfg.kinds.values() for p in decl.files}
    # A path beneath a symlinked directory is not asked about (git refuses it, #82): an entry
    # there is judged by its target, and a path whose link leaves the campaign is already a
    # `symlink-outside` finding.
    probe = set(named)
    for ents, _nm, _miss in per_kind.values():
        probe.update(e.path for e in ents)
        probe.update(e.target for e in ents if e.target)
    probe = {p for p in probe if not walker.beneath_link(p)}
    try:
        ignored, refused = git.ignored(sorted(probe))
    except GitIgnoreError as e:  # fail closed: unfiltered is not the same as unignored
        ignored, refused = set(), {}
        findings.append(Finding("gitignore-unchecked", f"git check-ignore could not run, so "
                                f"gitignored files were not filtered: {e}"))
    for p, why in sorted(refused.items()):
        findings.append(Finding("gitignore-unchecked",
                                f"git would not say whether this path is ignored: {why}", path=p))
    dropped = ignored - named_files
    for name, (ents, nm, miss) in per_kind.items():
        kept = [e for e in ents if e.path not in dropped]
        named.update(e.target for e in kept if e.target)  # a dropped link names nothing
        per_kind[name] = (kept, nm, miss)
    for p in sorted(ignored & named):
        findings.append(Finding("gitignored", "git ignores this path; mempalace would skip it "
                                "and `mp prune` would drop its drawers", path=p))

    # Rule 6 on the real files (R2): group by the resolved file, since that is what mempalace
    # dedups on. The mining kind is the single `mined_as` mark among the kinds reaching it.
    by_key: dict[str, set[str]] = {}
    for ents, _nm, _miss in per_kind.values():
        for e in ents:
            by_key.setdefault(e.key, set()).add(e.kind)
    mining: dict[str, str | None] = {}
    for key, kinds in sorted(by_key.items()):
        fs, chosen = shared_file_findings(key, [cfg.kinds[k] for k in sorted(kinds)])
        findings += fs
        mining[key] = chosen

    kinds: dict[str, ResolvedKind] = {}
    for name, decl in cfg.kinds.items():
        ents, nm, miss = per_kind[name]
        files = {}
        for e in ents:
            files[e.path] = ResolvedFile(e.path, e.sha256, e.minable, mining.get(e.key), e.target)
        kinds[name] = ResolvedKind(
            name, decl.standard, decl.trust,
            tuple(files[p] for p in sorted(files)), tuple(sorted(nm)), tuple(sorted(miss)),
        )

    # Rule 8: nothing resolved at all. A host where everything is merely not checked out is
    # not an empty corpus (R7), so not_materialized counts as "something declared".
    if not any(k.files or k.not_materialized for k in kinds.values()):
        findings.append(Finding("empty-corpus", "the declaration resolves to no files"))

    findings.sort(key=lambda f: (f.code, f.path or "", f.detail))
    return ResolvedCorpus(cfg.campaign, kinds, tuple(findings), git.state)

