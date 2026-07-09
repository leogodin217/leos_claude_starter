"""Note skill CLI.

Wraps the Obsidian CLI to manage typed notes (findings, features, questions,
retros, decisions, research) in an Obsidian vault.

Hybrid write model: new-note creation writes directly to the vault filesystem
(no contention since the target file does not exist yet). Operations on
existing notes (status flips, property sets, log appends) go through the
Obsidian CLI so the running GUI arbitrates. OneDrive sync conflicts cannot
occur between this skill and the Obsidian GUI for existing-file writes.

See SKILL.md for the full behavioral contract.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator, Literal

import yaml


# -----------------------------------------------------------------------------
# Controlled vocabularies (validated at write time)
# -----------------------------------------------------------------------------

NoteType = Literal["finding", "feature", "question", "retro", "decision", "research"]

# The `area` vocabulary is NOT a `Literal` here — it is sourced at runtime from
# `<vault_path>/meta/note-areas.md` (see `load_valid_areas`) so every repo
# pointed at the shared vault agrees without duplicating the list in code.

Severity = Literal["critical", "warning", "trivial"]
Kind = Literal["bug", "nit", "gap", "design"]
Priority = Literal["p0", "p1", "p2"]

VALID_SEVERITIES: tuple[str, ...] = ("critical", "warning", "trivial")
VALID_KINDS: tuple[str, ...] = ("bug", "nit", "gap", "design")
# `discovered-in` is a controlled context (how a finding surfaced). The free
# grouping slug (old `__<instance>` suffix) is now the separate `batch` field.
# Required for findings.
VALID_DISCOVERED_IN_CONTEXTS: tuple[str, ...] = (
    "qa",
    "code-review",
    "arch-design",
    "arch-review",
    "planning",
    "other",
)
VALID_PRIORITIES: tuple[str, ...] = ("p0", "p1", "p2")
VALID_TYPES: tuple[str, ...] = (
    "finding",
    "feature",
    "question",
    "retro",
    "decision",
    "research",
)

# Per-type allowed status values. Skill rejects any value not in the type's set.
STATUS_BY_TYPE: dict[NoteType, tuple[str, ...]] = {
    "finding": ("open", "resolved", "deferred"),
    "feature": ("proposed", "scheduled", "implemented", "deferred"),
    "question": ("open", "answered"),
    "retro": (),  # retros have no status
    "decision": ("active", "superseded"),
    "research": ("in-progress", "complete", "abandoned"),
}

# Initial status per type (omitted for retro).
INITIAL_STATUS: dict[str, str] = {
    "finding": "open",
    "feature": "proposed",
    "question": "open",
    "decision": "active",
    "research": "in-progress",
}

# Non-terminal (active) statuses for default list filtering.
ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        "open",
        "active",
        "proposed",
        "scheduled",
        "in-progress",
    }
)

# Per-type folder routing.
FOLDER_BY_TYPE: dict[NoteType, str] = {
    "finding": "findings",
    "feature": "features",
    "question": "questions",
    "retro": "retros",
    "decision": "decisions",
    "research": "research",
}


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Resolved skill configuration.

    Attributes:
        vault: Obsidian vault name (passed as `vault=<name>` to the CLI),
            resolved from --vault / NOTE_VAULT / the repo binding.
        obsidian_cli: Absolute path to the Obsidian CLI binary (the Windows
            `Obsidian.com` launcher, accessed from WSL via `/mnt/c/...`).
        repo_root: Absolute path to the active repo (used to validate
            `related-code` references on write).
        vault_path: Absolute path to the vault directory on the local
            filesystem (used for direct filesystem reads and new-note creation).
        repo: The current repo's key in the vault `repos` map, from the repo
            binding (`<repo_root>/.claude/note.json`). Stamped onto new notes;
            None only when a vault override is used without a binding.
        repos_map: Full `repo -> areas` map from the vault registry
            (`meta/note-areas.md`). Used to scope `area` per repo and to lint
            every note against its own repo's area list.
        valid_areas: Controlled `area` vocabulary for the CURRENT `repo`
            (`repos_map[repo]`); empty when `repo` is None.
    """

    vault: str
    obsidian_cli: Path
    repo_root: Path | None
    vault_path: Path
    repo: str | None
    repos_map: dict[str, tuple[str, ...]]
    valid_areas: tuple[str, ...]


def load_repos_map(vault_path: Path) -> dict[str, tuple[str, ...]]:
    """Load the `repo -> areas` registry from the shared vault.

    Reads `<vault_path>/meta/note-areas.md` and parses its YAML frontmatter
    `repos:` mapping (each key a repo admitted to this vault, each value that
    repo's controlled `area` list). Single source of truth across every repo
    pointed at this vault: it both admits repos (the REPO-UNREGISTERED gate)
    and scopes each repo's area vocabulary.

    Raises:
        ConfigError: When the file is absent, has no YAML frontmatter, lacks a
            `repos` key, or `repos` is not a mapping of repo -> non-empty
            list-of-strings.
    """
    areas_file = vault_path / "meta" / "note-areas.md"
    if not areas_file.exists():
        raise ConfigError(
            f"Vault registry file not found: {areas_file}. "
            "Create it with a YAML frontmatter `repos:` map (repo -> area list)."
        )
    with areas_file.open(encoding="utf-8") as f:
        if f.readline().strip() != "---":
            raise ConfigError(
                f"{areas_file} has no YAML frontmatter block (must start with '---')."
            )
        fm_lines: list[str] = []
        for line in f:
            if line.strip() == "---":
                break
            fm_lines.append(line)
    parsed = yaml.safe_load("".join(fm_lines))
    if not isinstance(parsed, dict) or "repos" not in parsed:
        raise ConfigError(f"{areas_file} frontmatter lacks a `repos` key.")
    repos = parsed["repos"]
    if not isinstance(repos, dict) or not repos:
        raise ConfigError(f"{areas_file} `repos` must be a non-empty mapping.")
    result: dict[str, tuple[str, ...]] = {}
    for repo, areas in repos.items():
        if (
            not isinstance(areas, list)
            or not areas
            or not all(isinstance(a, str) for a in areas)
        ):
            raise ConfigError(
                f"{areas_file} repos[{repo!r}] must be a non-empty list of strings."
            )
        result[str(repo)] = tuple(areas)
    return result


def _read_repo_binding(repo_root: Path | None) -> dict:
    """Read `<repo_root>/.claude/note.json` if present, else empty dict."""
    if repo_root is None:
        return {}
    binding_file = repo_root / ".claude" / "note.json"
    if not binding_file.exists():
        return {}
    try:
        parsed = json.loads(binding_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"Cannot read repo binding {binding_file}: {exc}")
    if not isinstance(parsed, dict):
        raise ConfigError(f"{binding_file} must be a JSON object.")
    return parsed


def load_config(
    vault_override: str | None = None,
    vault_path_override: str | None = None,
    repo_override: str | None = None,
) -> Config:
    """Resolve skill configuration through the three-layer binding.

    Three layers agree before any operation:
      - Repo binding  (`<repo_root>/.claude/note.json`): logical vault name +
        this repo's name in it. Committed, portable (no absolute paths).
      - Machine registry (`~/.config/note.json` `vaults:` map): vault name ->
        absolute path on this disk. Laptop-local.
      - Vault registry (`<vault_path>/meta/note-areas.md` `repos:` map): which
        repos are admitted, and each repo's area vocabulary.

    Four fail-closed gates (Principle #7 — fail closed, no default vault):
      1. UNBOUND          — no vault name (no --vault, NOTE_VAULT, or binding).
      2. VAULT-UNKNOWN    — vault name not in the machine `vaults:` map.
      3. REPO-UNREGISTERED — repo name not a key in the vault `repos:` map.
      4. AREA-INVALID     — enforced later, at write time, per repo.

    Args:
        vault_override: --vault flag value (highest precedence for the name).
        vault_path_override: --vault-path flag; bypasses the machine map.
        repo_override: --repo flag; bypasses the binding's repo (rare).

    Returns:
        Resolved Config (`repo` may be None only under a vault override with
        no binding; write ops that need it enforce presence themselves).

    Raises:
        ConfigError: On any of the four gates, a missing Obsidian CLI, or a
            missing / malformed vault registry.
    """
    # --- repo_root (git of cwd; per-repo, used to find the binding) ---
    repo_root: str | None = os.environ.get("REPO_ROOT")
    if repo_root is None:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            repo_root = result.stdout.strip()
    repo_root_path = Path(repo_root) if repo_root else None

    binding = _read_repo_binding(repo_root_path)

    # --- machine registry ---
    obsidian_cli: str | None = os.environ.get("OBSIDIAN_CLI")
    vaults_map: dict[str, str] = {}
    config_file = Path.home() / ".config" / "note.json"
    if config_file.exists():
        with config_file.open() as f:
            cfg = json.load(f)
        if obsidian_cli is None and "obsidian_cli" in cfg:
            obsidian_cli = cfg["obsidian_cli"]
        if isinstance(cfg.get("vaults"), dict):
            vaults_map = {str(k): str(v) for k, v in cfg["vaults"].items()}

    if obsidian_cli is None:
        pattern = "/mnt/c/Users/*/AppData/Local/Programs/Obsidian/Obsidian.com"
        matches = glob.glob(pattern)
        if not matches:
            raise ConfigError(
                "Cannot locate Obsidian CLI binary. "
                "Set OBSIDIAN_CLI env var or add obsidian_cli to ~/.config/note.json. "
                f"Auto-detect pattern: {pattern}"
            )
        obsidian_cli = matches[0]

    # --- Gate 1: vault name (UNBOUND) ---
    vault: str | None = (
        vault_override
        or os.environ.get("NOTE_VAULT")
        or (binding.get("vault") if binding else None)
    )
    if vault is None:
        raise ConfigError(
            "UNBOUND: this repo is not bound to a vault. "
            "Add .claude/note.json with {\"vault\": \"<name>\", \"repo\": \"<name>\"}, "
            "or pass --vault <name> / set NOTE_VAULT."
        )
    vault = str(vault)

    # --- Gate 2: vault path (VAULT-UNKNOWN) ---
    vault_path: str | None = (
        vault_path_override
        or os.environ.get("OBSIDIAN_VAULT_PATH")
        or vaults_map.get(vault)
    )
    if vault_path is None:
        known = ", ".join(sorted(vaults_map)) or "(none)"
        raise ConfigError(
            f"VAULT-UNKNOWN: vault {vault!r} is not in the machine registry. "
            f"Add it to ~/.config/note.json `vaults`, or pass --vault-path. "
            f"Known vaults: {known}"
        )

    repos_map = load_repos_map(Path(vault_path))

    # --- Gate 3: repo (REPO-UNREGISTERED) ---
    repo: str | None = repo_override or (binding.get("repo") if binding else None)
    if repo is not None:
        repo = str(repo)
        if repo not in repos_map:
            known = ", ".join(sorted(repos_map))
            raise ConfigError(
                f"REPO-UNREGISTERED: repo {repo!r} is not admitted to vault "
                f"{vault!r}. Register it in {vault_path}/meta/note-areas.md "
                f"`repos`. Admitted repos: {known}"
            )

    valid_areas = repos_map.get(repo, ()) if repo is not None else ()

    # `vault` defaults to the vault directory's name, which is how Obsidian
    # names a vault unless the user renamed it. Resolved after `vault_path`
    # because it derives from it.
    if vault is None:
        vault = Path(vault_path).name

    return Config(
        vault=vault,
        obsidian_cli=Path(obsidian_cli),
        repo_root=repo_root_path,
        vault_path=Path(vault_path),
        repo=repo,
        repos_map=repos_map,
        valid_areas=valid_areas,
    )


# -----------------------------------------------------------------------------
# Errors
# -----------------------------------------------------------------------------


class NoteSkillError(Exception):
    """Base class for all note-skill errors."""


class ConfigError(NoteSkillError):
    """Configuration resolution failed."""


class PreflightError(NoteSkillError):
    """Pre-flight check failed (vault unreachable, CLI missing, etc.)."""


class ValidationError(NoteSkillError):
    """A controlled-vocabulary value or cross-reference failed validation."""


class SlugResolutionError(NoteSkillError):
    """Slug did not resolve, or resolved ambiguously."""


# -----------------------------------------------------------------------------
# Obsidian CLI wrapper
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ObsidianResult:
    """Result of an Obsidian CLI invocation.

    Attributes:
        stdout: Captured standard output.
        stderr: Captured standard error.
        returncode: Process exit code (0 on success).
    """

    stdout: str
    stderr: str
    returncode: int


def obsidian(
    config: Config,
    command: str,
    args: dict[str, str | bool],
) -> ObsidianResult:
    """Invoke the Obsidian CLI with the given command and key=value args.

    Args:
        config: Skill configuration (provides CLI path and vault name).
        command: Obsidian CLI subcommand (e.g., "property:set",
            "files", "base:query", "search:context").
        args: CLI arguments as key→value pairs. Boolean True values become
            bare flags (e.g., `{"open": True}` becomes `open`); False values
            are omitted.

    Returns:
        ObsidianResult capturing stdout, stderr, and exit code.

    Raises:
        PreflightError: When the CLI binary cannot be invoked or times out.
    """
    cmd: list[str] = [str(config.obsidian_cli), command]
    for key, value in args.items():
        if isinstance(value, bool):
            if value:
                cmd.append(key)
            # False → omit
        else:
            cmd.append(f"{key}={value}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["pkill", "-9", "-f", "/init.*Obsidian"], capture_output=True)
        subprocess.run(["pkill", "-9", "-f", "Obsidian.com"], capture_output=True)
        raise PreflightError(
            f"Obsidian CLI '{command}' timed out after 30s and was killed. "
            "Verify Obsidian is running and not blocked by a dialog."
        )
    except FileNotFoundError as exc:
        raise PreflightError(
            f"Obsidian CLI binary not found at {config.obsidian_cli}"
        ) from exc
    except OSError as exc:
        raise PreflightError(
            f"Cannot invoke Obsidian CLI at {config.obsidian_cli}: {exc}"
        ) from exc

    return ObsidianResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def preflight(config: Config) -> None:
    """Verify the vault is reachable and free of sync conflicts.

    Side effects:
        Prints a warning to stderr for any `*Conflicted Copy*` files found.

    Raises:
        PreflightError: When the Obsidian CLI is not reachable, the vault
            cannot be opened, or vault_path does not exist.
    """
    # Check CLI binary exists.
    if not config.obsidian_cli.exists():
        raise PreflightError(f"Obsidian CLI not found at {config.obsidian_cli}")

    # Check vault_path exists and is a directory.
    if not config.vault_path.exists() or not config.vault_path.is_dir():
        raise PreflightError(
            f"vault_path {config.vault_path} does not exist or is not a directory."
        )

    # Check vault is accessible.
    result = obsidian(config, "files", {"vault": config.vault, "ext": "md"})
    if result.returncode != 0:
        raise PreflightError(
            f"Vault '{config.vault}' is not accessible. stderr: {result.stderr.strip()}"
        )

    # Check for conflicted copy files.
    files_output = result.stdout
    conflicted = [
        line for line in files_output.splitlines() if "Conflicted Copy" in line
    ]
    for conflict in conflicted:
        print(f"WARNING: Conflicted copy detected: {conflict}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Slug + path utilities
# -----------------------------------------------------------------------------


def slugify(title: str) -> str:
    """Convert a free-text title into a filename slug.

    Rules:
        - Lowercase.
        - Non-alphanumeric runs collapse to a single hyphen.
        - Leading/trailing hyphens stripped.
        - Empty result is an error.

    Args:
        title: Free-text title.

    Returns:
        URL-safe slug, no extension.

    Raises:
        ValidationError: When the resulting slug would be empty.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        raise ValidationError(
            f"Title {title!r} produces an empty slug after normalization."
        )
    return slug


def resolve_slug(config: Config, slug_or_prefix: str) -> Path:
    """Resolve a user-supplied slug to a vault-relative note path.

    Resolution uses filesystem glob over config.vault_path:
        1. Exact filename match (without `.md`) anywhere in the vault.
        2. Unique prefix match.
        3. Error if ambiguous, listing candidates as vault-relative paths.

    Args:
        config: Skill configuration.
        slug_or_prefix: Slug or unique prefix.

    Returns:
        Vault-relative path (e.g., Path("findings/state-store-resume-bug.md")).

    Raises:
        SlugResolutionError: When no match or multiple matches found.
    """
    all_md = list(config.vault_path.rglob("*.md"))
    # Convert to vault-relative paths.
    all_paths = [p.relative_to(config.vault_path) for p in all_md]

    # Exact match first.
    exact: list[Path] = []
    for vpath in all_paths:
        if vpath.stem == slug_or_prefix:
            exact.append(vpath)

    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        candidates = ", ".join(str(p) for p in exact)
        raise SlugResolutionError(
            f"Slug {slug_or_prefix!r} is ambiguous. Candidates: {candidates}"
        )

    # Prefix match.
    prefix_matches: list[Path] = []
    for vpath in all_paths:
        if vpath.stem.startswith(slug_or_prefix):
            prefix_matches.append(vpath)

    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        candidates = ", ".join(str(p) for p in prefix_matches)
        raise SlugResolutionError(
            f"Slug prefix {slug_or_prefix!r} is ambiguous. Candidates: {candidates}"
        )

    raise SlugResolutionError(
        f"No note found matching slug or prefix {slug_or_prefix!r}"
    )


def disambiguate_slug(config: Config, folder: str, slug: str) -> str:
    """Append `-2`, `-3`, ... to slug until unique within folder.

    Uses filesystem glob over config.vault_path.

    Args:
        config: Skill configuration.
        folder: Vault folder (e.g., "findings").
        slug: Candidate slug.

    Returns:
        A slug guaranteed not to collide with an existing file in folder.
    """
    folder_path = config.vault_path / folder
    existing_slugs: set[str] = set()
    if folder_path.exists():
        for p in folder_path.glob("*.md"):
            existing_slugs.add(p.stem)

    if slug not in existing_slugs:
        return slug

    counter = 2
    while True:
        candidate = f"{slug}-{counter}"
        if candidate not in existing_slugs:
            return candidate
        counter += 1


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_status(note_type: NoteType, status: str) -> None:
    """Verify status is legal for the given type.

    Raises:
        ValidationError: When status is not in STATUS_BY_TYPE[note_type].
    """
    allowed = STATUS_BY_TYPE.get(note_type, ())
    if not allowed:
        raise ValidationError(
            f"Note type {note_type!r} does not support status (e.g., retro). "
            f"Cannot set status {status!r}."
        )
    if status not in allowed:
        raise ValidationError(
            f"Status {status!r} is not valid for type {note_type!r}. "
            f"Allowed: {', '.join(allowed)}"
        )


def validate_area(area: str | None, valid_areas: tuple[str, ...]) -> None:
    """Verify area is in the vault-sourced vocabulary (or absent).

    Raises:
        ValidationError: When area is set but not in valid_areas.
    """
    if area is None:
        return
    if area not in valid_areas:
        raise ValidationError(
            f"Area {area!r} is not valid. Allowed: {', '.join(valid_areas)}"
        )


def validate_kind(kind: str | None) -> None:
    """Verify kind is in the controlled list (or absent).

    Raises:
        ValidationError: When kind is set but not a valid VALID_KINDS value.
    """
    if kind is None:
        return
    if kind not in VALID_KINDS:
        raise ValidationError(
            f"Kind {kind!r} is not valid. Allowed: {', '.join(VALID_KINDS)}"
        )


def validate_discovered_in(value: str | None) -> None:
    """Verify a discovered-in value is a controlled context (or absent).

    `discovered-in` is now a bare context — one of
    VALID_DISCOVERED_IN_CONTEXTS. The old `__<instance>` grouping suffix moved
    to the separate free-slug `batch` field.

    Raises:
        ValidationError: When the value is not a valid context.
    """
    if value is None or value == "":
        return
    if value not in VALID_DISCOVERED_IN_CONTEXTS:
        raise ValidationError(
            f"discovered-in {value!r} is not a valid context. "
            f"Allowed: {', '.join(VALID_DISCOVERED_IN_CONTEXTS)}. "
            "Put any grouping slug in the separate `batch` field."
        )


def validate_batch(value: str | None) -> None:
    """Verify a batch slug uses no colon (Obsidian renders colons as broken links).

    Raises:
        ValidationError: When the value contains ':'.
    """
    if value and ":" in value:
        raise ValidationError(
            f"batch value {value!r} contains ':'. Use '-' / '__' separators only."
        )


def validate_tags(tags: list[str]) -> None:
    """Verify every tag is a `planning-<slug>` workstream-membership tag.

    Tags are a closed vocabulary: the only legal tag is `planning-<slug>`
    (roadmap / workstream membership — the one facet no single-valued field
    can express). Topic, discovered-in, and kind information lives in the
    respective fields, not in tags.

    Raises:
        ValidationError: When any tag is not `planning-<non-empty-slug>`, or
            contains ':'.
    """
    bad = [
        t
        for t in tags
        if ":" in t or not t.startswith("planning-") or t == "planning-"
    ]
    if bad:
        raise ValidationError(
            f"tags must be `planning-<slug>` (workstream membership only): {bad}. "
            "Topic -> area/repo; how it surfaced -> discovered-in; "
            "finding kind -> kind. Everything else is dropped."
        )


def validate_code_paths(config: Config, paths: list[str]) -> None:
    """Verify each related-code reference exists under repo_root.

    Each path may include a `::symbol` suffix (ignored for existence check).

    Raises:
        ValidationError: When any path's file portion is missing.
    """
    if config.repo_root is None:
        if paths:
            raise ValidationError(
                "related-code cannot be validated: no repo checkout resolved "
                "(run inside the owning repo, or omit --code)."
            )
        return
    for path_spec in paths:
        # Strip optional ::symbol suffix.
        file_part = path_spec.split("::")[0]
        full_path = config.repo_root / file_part
        if not full_path.exists():
            raise ValidationError(
                f"related-code path {file_part!r} does not exist under repo_root "
                f"({config.repo_root}). Full path checked: {full_path}"
            )


def validate_wikilinks(config: Config, links: list[str]) -> None:
    """Verify each wikilink target resolves to an existing vault note.

    Args:
        links: Strings shaped like "[[note-slug]]" or "[[note-slug|alias]]".

    Raises:
        ValidationError: When any target slug does not resolve in the vault.
    """
    existing_slugs: set[str] = {p.stem for p in config.vault_path.rglob("*.md")}

    for link in links:
        # Extract slug from [[slug]] or [[slug|alias]].
        match = re.match(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", link)
        if not match:
            raise ValidationError(
                f"Wikilink {link!r} is not in [[slug]] or [[slug|alias]] format."
            )
        target_slug = match.group(1).strip()
        if target_slug not in existing_slugs:
            raise ValidationError(
                f"Wikilink target {target_slug!r} does not exist in vault {config.vault!r}. "
                f"Link: {link}"
            )


# -----------------------------------------------------------------------------
# Note creation
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class NewNoteSpec:
    """Inputs for creating a new note.

    Attributes:
        note_type: Controlled type.
        title: Free-text title (becomes H1 and basis for slug).
        area: Optional package area.
        severity: Required for findings, otherwise None.
        kind: Required for findings, otherwise None.
        priority: Optional, features only.
        related_code: Repo-relative paths (with optional `::symbol`).
        related_notes: Wikilink strings (e.g., `"[[other-note]]"`).
        tags: Free-form tags.
        body: Optional initial body content (appended after template sections).
        sprint: Required for retros (repo path to sprint plan).
        sprint_end: Required for retros (ISO date).
        decided_on: Required for decisions (ISO date).
        sources: Optional URLs for research notes.
        blocking: Optional, questions only.
        discovered_in: Context where the finding surfaced. Required for
            findings, otherwise None.
    """

    note_type: NoteType
    title: str
    repo: str | None
    area: str | None
    severity: Severity | None
    kind: str | None
    priority: Priority | None
    related_code: list[str]
    related_notes: list[str]
    tags: list[str]
    body: str | None
    sprint: str | None
    sprint_end: date | None
    decided_on: date | None
    sources: list[str]
    blocking: bool | None
    discovered_in: str | None
    batch: str | None
    forward: bool


def _yaml_list(items: list[str]) -> str:
    """Render a YAML list as an indented block.

    Uses yaml.safe_dump to produce correct quoting, then indents two spaces
    so the result composes under a key like `related-notes:<_yaml_list(...)>`.
    Bare wikilinks like `[[name]]` would otherwise be parsed back as nested
    flow sequences.
    """
    if not items:
        return "[]"
    inner = yaml.safe_dump(items, default_flow_style=False, allow_unicode=True).rstrip(
        "\n"
    )
    lines = [""] + ["  " + line for line in inner.split("\n")]
    return "\n".join(lines)


def render_frontmatter(spec: NewNoteSpec, today: date) -> str:
    """Render the YAML frontmatter block for a new note.

    Includes core fields (`type`, `status`, `created`, `updated`, optional
    `area`, `tags`, `related-notes`) plus type-specific extensions per the
    schema in SKILL.md. `status` defaults to the type's initial value:
    `open` (finding/question), `proposed` (feature), `active` (decision),
    `in-progress` (research), or omitted (retro).

    Args:
        spec: Validated note inputs.
        today: Date to use for `created` and `updated`.

    Returns:
        YAML frontmatter as a string, including leading and trailing `---`.
    """
    lines: list[str] = ["---"]
    lines.append(f"type: {spec.note_type}")

    # Status: omit for retro, else use initial value.
    if spec.note_type != "retro":
        initial_status = INITIAL_STATUS[spec.note_type]
        lines.append(f"status: {initial_status}")

    lines.append(f"created: {today.isoformat()}")
    lines.append(f"updated: {today.isoformat()}")

    if spec.repo is not None:
        lines.append(f"repo: {spec.repo}")

    if spec.area is not None:
        lines.append(f"area: {spec.area}")

    # Per-type extensions.
    if spec.note_type == "finding":
        lines.append(f"severity: {spec.severity}")
        lines.append(f"kind: {spec.kind}")
        if spec.discovered_in is not None:
            lines.append(f"discovered-in: {spec.discovered_in}")
        if spec.batch is not None:
            lines.append(f"batch: {spec.batch}")

    if spec.forward:
        lines.append("forward: true")

    if spec.tags:
        lines.append(f"tags:{_yaml_list(spec.tags)}")

    if spec.related_notes:
        lines.append(f"related-notes:{_yaml_list(spec.related_notes)}")

    # Remaining per-type extensions.
    if spec.note_type == "finding":
        if spec.related_code:
            lines.append(f"related-code:{_yaml_list(spec.related_code)}")

    elif spec.note_type == "feature":
        if spec.priority is not None:
            lines.append(f"priority: {spec.priority}")
        if spec.related_code:
            lines.append(f"related-code:{_yaml_list(spec.related_code)}")

    elif spec.note_type == "question":
        if spec.blocking is not None:
            lines.append(f"blocking: {str(spec.blocking).lower()}")

    elif spec.note_type == "retro":
        lines.append(f"sprint: {spec.sprint}")
        lines.append(f"sprint-end: {spec.sprint_end.isoformat()}")

    elif spec.note_type == "decision":
        lines.append(f"decided-on: {spec.decided_on.isoformat()}")

    elif spec.note_type == "research":
        if spec.sources:
            lines.append(f"sources:{_yaml_list(spec.sources)}")

    lines.append("---")
    return "\n".join(lines)


def render_body_template(spec: NewNoteSpec, today: date) -> str:
    """Render the per-type body template.

    All types receive an H1 title and a `## Log` section seeded with a
    creation entry. Findings additionally get `## Problem` and `## Analysis`;
    features get `## Motivation` and `## Sketch`; decisions get
    `## Context`, `## Decision`, `## Alternatives`; etc. (see SKILL.md).

    Args:
        spec: Validated note inputs.
        today: Date for the initial Log entry.

    Returns:
        Markdown body as a string.
    """
    lines: list[str] = [f"# {spec.title}", ""]

    if spec.note_type == "finding":
        lines += ["## Problem", "", "## Analysis", ""]
    elif spec.note_type == "feature":
        lines += ["## Motivation", "", "## Sketch", ""]
    elif spec.note_type == "question":
        lines += ["## Context", ""]
    elif spec.note_type == "retro":
        lines += [
            "## What Went Well",
            "",
            "## What Could Improve",
            "",
            "## Action Items",
            "",
        ]
    elif spec.note_type == "decision":
        lines += ["## Context", "", "## Decision", "", "## Alternatives", ""]
    elif spec.note_type == "research":
        lines += ["## Summary", "", "## Notes", ""]

    if spec.body is not None:
        lines += [spec.body, ""]

    lines += ["## Log", f"- {today.isoformat()}: created"]

    return "\n".join(lines)


def cmd_new(config: Config, spec: NewNoteSpec, no_open: bool = False) -> Path:
    """Create a new note via direct filesystem write.

    Steps:
        1. preflight(config).
        2. Validate severity/kind/discovered-in/sprint/decided_on requirements
           per type.
        3. validate_area, validate_code_paths, validate_wikilinks.
        4. slugify(title), then disambiguate against the type's folder.
        5. Render frontmatter + body with real newlines (no escaping).
        6. Write atomically: write to <target>.tmp then os.replace to target.
        7. Open in GUI unless suppressed.

    Args:
        config: Skill configuration.
        spec: Validated note inputs.
        no_open: When True, skip opening the note in the Obsidian GUI.

    Returns:
        Vault-relative path of the created note.

    Raises:
        ValidationError: On any schema or cross-reference violation.
        PreflightError: On vault inaccessibility.
    """
    preflight(config)

    # Step 2: Type-specific required field validation.
    if spec.note_type == "finding":
        if spec.severity is None:
            raise ValidationError(
                "field=severity is required for type=finding. "
                f"Use --severity {{{'|'.join(VALID_SEVERITIES)}}}."
            )
        if spec.severity not in VALID_SEVERITIES:
            raise ValidationError(
                f"field=severity value={spec.severity!r} is not valid. "
                f"Allowed: {', '.join(VALID_SEVERITIES)}"
            )
        if spec.kind is None:
            raise ValidationError(
                "field=kind is required for type=finding. "
                f"Use --kind {{{'|'.join(VALID_KINDS)}}}."
            )
        validate_kind(spec.kind)
        if spec.discovered_in is None or spec.discovered_in == "":
            raise ValidationError(
                "field=discovered-in is required for type=finding. "
                "Use --discovered-in <context>[__<instance>], context one of "
                f"{{{'|'.join(VALID_DISCOVERED_IN_CONTEXTS)}}}."
            )
        validate_discovered_in(spec.discovered_in)

    if spec.note_type == "retro":
        if spec.sprint is None:
            raise ValidationError(
                "field=sprint is required for type=retro (repo path to sprint plan)."
            )
        if spec.sprint_end is None:
            raise ValidationError(
                "field=sprint-end is required for type=retro (ISO date)."
            )

    if spec.note_type == "decision":
        if spec.decided_on is None:
            raise ValidationError(
                "field=decided-on is required for type=decision (ISO date)."
            )

    if spec.priority is not None and spec.priority not in VALID_PRIORITIES:
        raise ValidationError(
            f"field=priority value={spec.priority!r} is not valid. "
            f"Allowed: {', '.join(VALID_PRIORITIES)}"
        )

    # Step 3: Cross-reference validation.
    if spec.repo is None:
        raise ValidationError(
            "repo is unresolved: cannot create a note without a repo binding. "
            "Add .claude/note.json to this repo, or pass --repo <name>."
        )
    if spec.area is None:
        raise ValidationError(
            "field=area is required. Use --area with one of: "
            f"{', '.join(config.valid_areas)}"
        )
    validate_area(spec.area, config.valid_areas)
    validate_batch(spec.batch)
    validate_tags(spec.tags)
    validate_code_paths(config, spec.related_code)
    validate_wikilinks(config, spec.related_notes)

    # Step 4: Slug generation.
    slug = slugify(spec.title)
    folder = FOLDER_BY_TYPE[spec.note_type]
    slug = disambiguate_slug(config, folder, slug)
    vault_relpath = Path(f"{folder}/{slug}.md")

    # Step 5: Render with real newlines.
    today = date.today()
    frontmatter = render_frontmatter(spec, today)
    body = render_body_template(spec, today)
    full_content = f"{frontmatter}\n{body}\n"

    # Step 6: Atomic write.
    target = config.vault_path / vault_relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(full_content, encoding="utf-8")
    os.replace(tmp, target)

    # Step 7: Open in GUI.
    if not no_open:
        obsidian(config, "open", {"vault": config.vault, "path": str(vault_relpath)})

    return vault_relpath


# -----------------------------------------------------------------------------
# Status transitions
# -----------------------------------------------------------------------------


def _read_note_property(config: Config, vault_path: Path, name: str) -> str:
    """Read a single frontmatter property from a note."""
    result = obsidian(
        config,
        "property:read",
        {"vault": config.vault, "path": str(vault_path), "name": name},
    )
    if result.returncode != 0:
        raise PreflightError(
            f"Cannot read property {name!r} from {vault_path}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _note_has_log_section(config: Config, vault_path: Path) -> bool:
    """Check if the note has a ## Log section."""
    result = obsidian(
        config,
        "read",
        {"vault": config.vault, "path": str(vault_path)},
    )
    if result.returncode != 0:
        return False
    return "## Log" in result.stdout


def cmd_status(
    config: Config,
    slug: str,
    new_status: str,
    reason: str | None,
) -> None:
    """Flip a note's status, append a Log entry, bump `updated`.

    Steps:
        1. preflight(config).
        2. resolve_slug(slug).
        3. Read current `type` and `status` via `obsidian property:read`.
        4. validate_status(type, new_status).
        5. `obsidian property:set name=status value=<new>`.
        6. `obsidian property:set name=updated value=<today>`.
        7. Append `- <today>: <old> → <new> (<reason>)` to `## Log` section
           (creating the section if absent).

    Args:
        config: Skill configuration.
        slug: Slug or unique prefix.
        new_status: Target status (validated against the resolved type).
        reason: Optional free-text reason recorded in the Log entry.

    Raises:
        SlugResolutionError: When slug does not resolve.
        ValidationError: When new_status is not legal for the note's type.
    """
    preflight(config)

    vault_path = resolve_slug(config, slug)
    note_type_str = _read_note_property(config, vault_path, "type")
    old_status = _read_note_property(config, vault_path, "status")

    # Cast to NoteType for validation.
    if note_type_str not in VALID_TYPES:
        raise ValidationError(
            f"Note at {vault_path} has unknown type {note_type_str!r}."
        )
    note_type: NoteType = note_type_str  # type: ignore[assignment]

    validate_status(note_type, new_status)

    today = date.today().isoformat()

    # Update status.
    result = obsidian(
        config,
        "property:set",
        {
            "vault": config.vault,
            "path": str(vault_path),
            "name": "status",
            "value": new_status,
            "type": "text",
        },
    )
    if result.returncode != 0:
        raise PreflightError(
            f"Failed to set status on {vault_path}: {result.stderr.strip()}"
        )

    # Update updated date.
    result = obsidian(
        config,
        "property:set",
        {
            "vault": config.vault,
            "path": str(vault_path),
            "name": "updated",
            "value": today,
            "type": "date",
        },
    )
    if result.returncode != 0:
        raise PreflightError(
            f"Failed to set updated on {vault_path}: {result.stderr.strip()}"
        )

    # Append log entry.
    log_entry = f"- {today}: {old_status} → {new_status}"
    if reason is not None:
        log_entry += f" ({reason})"

    has_log = _note_has_log_section(config, vault_path)
    if has_log:
        append_content = f"\\n{log_entry}"
    else:
        append_content = f"\\n\\n## Log\\n{log_entry}"

    result = obsidian(
        config,
        "append",
        {
            "vault": config.vault,
            "path": str(vault_path),
            "content": append_content,
        },
    )
    if result.returncode != 0:
        raise PreflightError(
            f"Failed to append log entry to {vault_path}: {result.stderr.strip()}"
        )


# -----------------------------------------------------------------------------
# Field updates
# -----------------------------------------------------------------------------


# Fields whose values are YAML lists. `set` accepts multiple values and
# rewrites the frontmatter via direct filesystem write (atomic).
LIST_FIELDS: frozenset[str] = frozenset(
    {
        "tags",
        "related-notes",
        "related-code",
        "depends-on",
        "sources",
    }
)


def _rewrite_frontmatter(file_path: Path, fm_mutator) -> None:
    """Atomically rewrite a note's frontmatter via direct filesystem write.

    Reads the file, parses YAML frontmatter, calls fm_mutator(dict) to
    mutate the dict in place, re-serializes the frontmatter, and writes the
    result back via a temp file + os.replace.

    Used for list-valued field updates because the Obsidian CLI's
    `property:set` does not cleanly support multi-value list writes.

    Args:
        file_path: Absolute path to the note file.
        fm_mutator: Callable that receives the parsed frontmatter dict and
            mutates it in place. Return value is ignored.

    Raises:
        ValidationError: If the file lacks a parseable frontmatter block.
    """
    content = file_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?\n)---\n?(.*)$", content, re.DOTALL)
    if match is None:
        raise ValidationError(f"{file_path} has no parseable YAML frontmatter block.")
    yaml_str, body = match.group(1), match.group(2)
    fm = yaml.safe_load(yaml_str) or {}
    if not isinstance(fm, dict):
        raise ValidationError(f"{file_path} frontmatter does not parse to a mapping.")

    fm_mutator(fm)

    new_yaml = yaml.safe_dump(
        fm,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    new_content = f"---\n{new_yaml}---\n{body}"

    tmp = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp.write_text(new_content, encoding="utf-8")
    os.replace(tmp, file_path)


def cmd_set(config: Config, slug: str, field: str, value: list[str]) -> None:
    """Update a single frontmatter field.

    Scalar fields (`status`, `area`, `severity`, `priority`, dates, booleans,
    text fields) require exactly one value and are written via the Obsidian
    CLI so the running GUI arbitrates.

    List fields (`tags`, `related-notes`, `related-code`, `depends-on`,
    `sources`) accept one or more values and replace the existing list in
    full. Written via direct filesystem rewrite with atomic rename.

    Validation:
        - `type` cannot be set via this command (raises ValidationError).
        - `status` revalidated against the note's current type.
        - `area` validated against the controlled list.
        - `severity`, `kind`, `priority` validated against their controlled
          lists.
        - `discovered-in` context prefix validated.
        - `related-notes` validated via validate_wikilinks.
        - `related-code` validated via validate_code_paths.

    Args:
        config: Skill configuration.
        slug: Slug or unique prefix.
        field: Frontmatter field name.
        value: One or more values. Scalar fields require exactly one.

    Raises:
        SlugResolutionError: When slug does not resolve.
        ValidationError: On controlled-field violation, multi-value scalar,
            or attempted type change.
    """
    preflight(config)

    if field in ("type", "repo"):
        raise ValidationError(
            f"field={field} is immutable provenance and cannot be changed via "
            "set (repo is stamped at creation; type would require a folder move)."
        )

    vault_path = resolve_slug(config, slug)
    abs_path = config.vault_path / vault_path

    is_list_field = field in LIST_FIELDS

    if is_list_field:
        if field == "related-notes":
            validate_wikilinks(config, value)
        elif field == "related-code":
            validate_code_paths(config, value)
        elif field == "tags":
            validate_tags(value)

        today = date.today()

        def _mutate(fm: dict) -> None:
            fm[field] = list(value)
            fm["updated"] = today

        _rewrite_frontmatter(abs_path, _mutate)
        return

    # Scalar path: require exactly one value.
    if len(value) != 1:
        raise ValidationError(
            f"field={field!r} is a scalar; expected one value, got {len(value)}. "
            f"List fields are: {', '.join(sorted(LIST_FIELDS))}."
        )
    scalar_value = value[0]

    if field == "status":
        note_type_str = _read_note_property(config, vault_path, "type")
        if note_type_str not in VALID_TYPES:
            raise ValidationError(
                f"Note at {vault_path} has unknown type {note_type_str!r}."
            )
        note_type: NoteType = note_type_str  # type: ignore[assignment]
        validate_status(note_type, scalar_value)

    elif field == "area":
        # Validate against the NOTE's own repo's area list (may differ from the
        # current checkout's repo in a shared vault).
        note_repo = _read_note_property(config, vault_path, "repo")
        repo_areas = config.repos_map.get(note_repo)
        if repo_areas is None:
            raise ValidationError(
                f"Note at {vault_path} has repo {note_repo!r} not in the vault "
                f"registry. Admitted repos: {', '.join(sorted(config.repos_map))}."
            )
        validate_area(scalar_value, repo_areas)

    elif field == "batch":
        validate_batch(scalar_value)

    elif field == "severity":
        if scalar_value not in VALID_SEVERITIES:
            raise ValidationError(
                f"field=severity value={scalar_value!r} is not valid. "
                f"Allowed: {', '.join(VALID_SEVERITIES)}"
            )

    elif field == "kind":
        validate_kind(scalar_value)

    elif field == "discovered-in":
        validate_discovered_in(scalar_value)

    elif field == "priority":
        if scalar_value not in VALID_PRIORITIES:
            raise ValidationError(
                f"field=priority value={scalar_value!r} is not valid. "
                f"Allowed: {', '.join(VALID_PRIORITIES)}"
            )

    # Determine property type for CLI.
    date_fields = {"created", "updated", "sprint-end", "decided-on"}
    bool_fields = {"blocking", "forward"}
    prop_type = "text"
    if field in date_fields:
        prop_type = "date"
    elif field in bool_fields:
        prop_type = "checkbox"

    result = obsidian(
        config,
        "property:set",
        {
            "vault": config.vault,
            "path": str(vault_path),
            "name": field,
            "value": scalar_value,
            "type": prop_type,
        },
    )
    if result.returncode != 0:
        raise PreflightError(
            f"Failed to set field {field!r} on {vault_path}: {result.stderr.strip()}"
        )

    # Bump updated timestamp.
    today = date.today().isoformat()
    obsidian(
        config,
        "property:set",
        {
            "vault": config.vault,
            "path": str(vault_path),
            "name": "updated",
            "value": today,
            "type": "date",
        },
    )


# -----------------------------------------------------------------------------
# Listing and querying
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class NoteSummary:
    """Compact note descriptor returned by list/query operations.

    Attributes:
        slug: Filename without `.md`.
        path: Vault-relative path.
        note_type: Controlled type.
        status: Current status (or empty for retros).
        area: area value, or None if unset.
        title: H1 title (or first non-frontmatter line).
        severity: For findings, else None.
        kind: For findings, else None.
        discovered_in: For findings, else None.
        priority: For features, else None.
        created: Creation date.
        updated: Last-update date.
        tags: Free-form tags (empty list if unset).
    """

    slug: str
    path: Path
    note_type: NoteType
    status: str
    repo: str | None
    area: str | None
    title: str
    severity: Severity | None
    kind: str | None
    discovered_in: str | None
    batch: str | None
    forward: bool
    priority: Priority | None
    created: date
    updated: date
    tags: tuple[str, ...]


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from note content."""
    if not content.startswith("---"):
        return {}
    # Find closing ---.
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    yaml_str = content[3:end].strip()
    parsed = yaml.safe_load(yaml_str)
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _extract_title(content: str) -> str:
    """Extract H1 title from note body (after frontmatter)."""
    past_frontmatter = False
    dash_count = 0
    for line in content.splitlines():
        if not past_frontmatter:
            if line.strip() == "---":
                dash_count += 1
                if dash_count == 2:
                    past_frontmatter = True
            continue
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _parse_frontmatter_from_file(file_path: Path) -> dict:
    """Read just the frontmatter block from a file without loading full content.

    Opens the file and reads until the closing `---` line (or EOF).
    Returns parsed YAML dict, or empty dict if frontmatter is absent or
    unparseable.
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            first_line = f.readline()
            if first_line.strip() != "---":
                return {}
            fm_lines: list[str] = []
            for line in f:
                if line.strip() == "---":
                    break
                fm_lines.append(line)
            yaml_str = "".join(fm_lines)
            parsed = yaml.safe_load(yaml_str)
            if not isinstance(parsed, dict):
                return {}
            return parsed
    except Exception:
        return {}


def _extract_title_from_file(file_path: Path) -> str:
    """Extract H1 title from a file without loading full content."""
    try:
        with file_path.open(encoding="utf-8") as f:
            past_frontmatter = False
            dash_count = 0
            for line in f:
                if not past_frontmatter:
                    if line.strip() == "---":
                        dash_count += 1
                        if dash_count == 2:
                            past_frontmatter = True
                    continue
                if line.startswith("# "):
                    return line[2:].strip()
    except Exception:
        pass
    return ""


def iter_all_notes(config: Config) -> Iterator[tuple[Path, dict]]:
    """Yield (absolute-path, frontmatter-dict) for every note in the vault.

    Iterates each per-type folder in FOLDER_BY_TYPE (skipping any that do
    not exist on disk) and yields the absolute file path alongside the
    parsed frontmatter dict. Notes with absent or unparseable frontmatter
    yield an empty dict.

    Args:
        config: Skill configuration.

    Yields:
        Tuples of (absolute path, frontmatter dict).
    """
    for type_folder in FOLDER_BY_TYPE.values():
        folder = config.vault_path / type_folder
        if not folder.exists():
            continue
        for md in sorted(folder.glob("*.md")):
            yield md, _parse_frontmatter_from_file(md)


def _read_note_summary_from_fs(vault_path: Path, file_path: Path) -> NoteSummary | None:
    """Read and parse a note into a NoteSummary using filesystem access."""
    vault_relpath = file_path.relative_to(vault_path)
    fm = _parse_frontmatter_from_file(file_path)
    if not fm:
        return None

    note_type_str = fm.get("type", "")
    if note_type_str not in VALID_TYPES:
        return None
    note_type: NoteType = note_type_str  # type: ignore[assignment]

    status_val = fm.get("status", "")

    repo_val = fm.get("repo")
    if repo_val == "" or repo_val is None:
        repo_val = None
    else:
        repo_val = str(repo_val)

    area_val = fm.get("area")
    if area_val == "" or area_val is None:
        area_val = None

    batch_val = fm.get("batch")
    if batch_val == "" or batch_val is None:
        batch_val = None
    else:
        batch_val = str(batch_val)

    forward_val = bool(fm.get("forward", False))

    severity_val = fm.get("severity")
    if severity_val not in VALID_SEVERITIES:
        severity_val = None

    kind_val = fm.get("kind")
    if kind_val not in VALID_KINDS:
        kind_val = None

    discovered_in_val = fm.get("discovered-in")
    if discovered_in_val == "" or discovered_in_val is None:
        discovered_in_val = None
    else:
        discovered_in_val = str(discovered_in_val)

    priority_val = fm.get("priority")
    if priority_val not in VALID_PRIORITIES:
        priority_val = None

    created_val = fm.get("created")
    updated_val = fm.get("updated")

    if created_val is None or updated_val is None:
        return None

    # Dates may come back as date objects from PyYAML.
    if isinstance(created_val, str):
        created_date = date.fromisoformat(created_val)
    else:
        created_date = created_val

    if isinstance(updated_val, str):
        updated_date = date.fromisoformat(updated_val)
    else:
        updated_date = updated_val

    title = _extract_title_from_file(file_path)
    slug = file_path.stem

    tags_val = fm.get("tags") or []
    if not isinstance(tags_val, list):
        tags_val = []
    tags_tuple = tuple(str(t) for t in tags_val)

    return NoteSummary(
        slug=slug,
        path=vault_relpath,
        note_type=note_type,
        status=status_val,
        repo=repo_val,
        area=area_val,
        title=title,
        severity=severity_val,  # type: ignore[arg-type]
        kind=kind_val,
        discovered_in=discovered_in_val,
        batch=batch_val,
        forward=forward_val,
        priority=priority_val,  # type: ignore[arg-type]
        created=created_date,
        updated=updated_date,
        tags=tags_tuple,
    )


def _severity_sort_key(severity: str | None) -> int:
    """Sort severities: critical=0, warning=1, trivial=2, None=3."""
    order = {"critical": 0, "warning": 1, "trivial": 2}
    if severity is None:
        return 3
    return order.get(severity, 3)


def _priority_sort_key(priority: str | None) -> int:
    """Sort priorities: p0=0, p1=1, p2=2, None=3."""
    order = {"p0": 0, "p1": 1, "p2": 2}
    if priority is None:
        return 3
    return order.get(priority, 3)


def cmd_list(
    config: Config,
    note_type: NoteType | None,
    status: str | None,
    area: str | None,
    needs_triage: bool,
    tags: list[str] | None,
    kind: str | None,
    discovered_in: str | None,
    repo: str | None = None,
    forward: bool = False,
) -> list[NoteSummary]:
    """List notes by filter using filesystem scanning.

    Behavior:
        - Default (no status filter): all notes with a non-terminal status
          (open, active, proposed, scheduled, in-progress).
        - `status="all"` disables the status filter entirely (every status).
        - `needs_triage` selects notes whose `area` is empty.
        - `tags` requires every listed tag to be present (AND semantics).
        - `kind` filters findings by their controlled kind value.
        - `discovered_in` filters findings by their `discovered-in` slug.
        - Filter combinations are AND.
        - Files with missing or unparseable frontmatter are silently skipped.

    Args:
        config: Skill configuration.
        note_type: Optional type filter.
        status: Optional status filter. `"all"` lists every status; otherwise
            validated against type if both given.
        area: Optional area filter.
        needs_triage: When True, restricts to notes missing `area`.
        tags: Optional tag filter; all listed tags must be present.
        kind: Optional kind filter (findings).
        discovered_in: Optional `discovered-in` filter (findings).

    Returns:
        Notes matching all filters, sorted by (severity desc, priority asc,
        created desc) where applicable.

    Raises:
        ValidationError: When status is given but not legal for note_type,
            or when kind is given but not a valid VALID_KINDS value.
    """
    list_all_statuses = status == "all"
    if status is not None and not list_all_statuses and note_type is not None:
        validate_status(note_type, status)
    if kind is not None:
        validate_kind(kind)

    # Determine which folders to scan.
    if note_type is not None:
        folders = [FOLDER_BY_TYPE[note_type]]
    else:
        folders = list(FOLDER_BY_TYPE.values())

    summaries: list[NoteSummary] = []
    for folder in folders:
        folder_path = config.vault_path / folder
        if not folder_path.exists():
            continue
        for file_path in folder_path.glob("*.md"):
            summary = _read_note_summary_from_fs(config.vault_path, file_path)
            if summary is None:
                continue

            # Apply type filter.
            if note_type is not None and summary.note_type != note_type:
                continue

            # Apply status filter.
            if list_all_statuses:
                pass
            elif status is not None:
                if summary.status != status:
                    continue
            else:
                # Default: only non-terminal statuses.
                if (
                    summary.status not in ACTIVE_STATUSES
                    and summary.note_type != "retro"
                ):
                    continue

            # Apply area filter.
            if area is not None and summary.area != area:
                continue

            # Apply needs_triage filter.
            if needs_triage and summary.area is not None:
                continue

            # Apply tags filter (AND semantics).
            if tags is not None and not set(tags).issubset(set(summary.tags)):
                continue

            # Apply kind filter (findings).
            if kind is not None and summary.kind != kind:
                continue

            # Apply discovered-in filter (findings).
            if discovered_in is not None and summary.discovered_in != discovered_in:
                continue

            # Apply repo filter.
            if repo is not None and summary.repo != repo:
                continue

            # Apply forward filter.
            if forward and not summary.forward:
                continue

            summaries.append(summary)

    # Sort: severity desc (critical first), priority asc (p0 first), created desc.
    summaries.sort(
        key=lambda s: (
            _severity_sort_key(s.severity),
            _priority_sort_key(s.priority),
            # Negate date for desc ordering using isoformat string negation workaround.
            str(-s.created.toordinal()),
        )
    )

    return summaries


def cmd_path(config: Config, slug: str) -> Path:
    """Print the absolute filesystem path of a note and return it.

    Args:
        config: Skill configuration.
        slug: Slug or unique prefix.

    Returns:
        Absolute path to the note file.

    Raises:
        SlugResolutionError: When slug does not resolve.
    """
    vault_relpath = resolve_slug(config, slug)
    abs_path = config.vault_path / vault_relpath
    print(abs_path)
    return abs_path


def cmd_search(config: Config, query: str) -> str:
    """Full-text vault search via `obsidian search:context`.

    Args:
        config: Skill configuration.
        query: Search query (case-insensitive).

    Returns:
        Search results with line context (text format).
    """
    result = obsidian(
        config,
        "search:context",
        {"vault": config.vault, "query": query},
    )
    return result.stdout


def cmd_moc(
    config: Config, view_name: str, output_format: Literal["json", "md"]
) -> str:
    """Run a Bases view query and return the result.

    Wraps `obsidian base:query view=<name> format=<format>`. The skill does
    not parse JSON results; that is the caller's responsibility.

    Args:
        config: Skill configuration.
        view_name: Base view name (matches a view in any base file under
            `MOCs/`).
        output_format: Either "json" or "md".

    Returns:
        Raw query output.

    Raises:
        PreflightError: When the view does not exist.
    """
    result = obsidian(
        config,
        "base:query",
        {"vault": config.vault, "view": view_name, "format": output_format},
    )
    if result.returncode != 0:
        raise PreflightError(
            f"MOC view {view_name!r} not found or query failed: {result.stderr.strip()}"
        )
    return result.stdout


def cmd_open(config: Config, slug: str) -> None:
    """Open a note in the Obsidian GUI.

    Args:
        config: Skill configuration.
        slug: Slug or unique prefix.

    Raises:
        SlugResolutionError: When slug does not resolve.
    """
    vault_path = resolve_slug(config, slug)
    obsidian(
        config,
        "open",
        {"vault": config.vault, "path": str(vault_path)},
    )


def cmd_check(config: Config) -> None:
    """Run pre-flight only and print a status summary."""
    preflight(config)
    print(f"vault:        {config.vault}")
    print(f"vault_path:   {config.vault_path}")
    print(f"repo:         {config.repo}")
    print(f"repo_root:    {config.repo_root}")
    print(f"obsidian_cli: {config.obsidian_cli}")
    print("OK")


def cmd_tags(config: Config, output_format: Literal["text", "json"]) -> str:
    """Aggregate tag usage across all vault notes.

    Iterates every note via iter_all_notes, collects each note's `tags`
    list, and tallies per-tag occurrences.

    Args:
        config: Skill configuration.
        output_format: "text" (one line per tag, count desc) or "json".

    Returns:
        Formatted output. Sorted by count descending, ties alphabetical.
    """
    counts: dict[str, int] = {}
    for _path, fm in iter_all_notes(config):
        tags = fm.get("tags") or []
        if not isinstance(tags, list):
            continue
        for tag in tags:
            tag_str = str(tag)
            counts[tag_str] = counts.get(tag_str, 0) + 1

    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    if output_format == "json":
        return json.dumps([{"tag": t, "count": c} for t, c in items], indent=2)

    if not items:
        return "(no tags)"
    width = max(len(t) for t, _ in items)
    return "\n".join(f"{t.ljust(width)}  {c}" for t, c in items)


def cmd_lint(config: Config) -> int:
    """Validate every note's frontmatter against the controlled schema.

    Checks per note:
        - `repo` is set and admitted to the vault (`config.repos_map`).
        - `area` is set and in the note's OWN repo's area list.
        - `status` is set (except retros) and valid for the note's type.
        - `severity` / `kind` set and valid for findings.
        - `discovered-in` is set on findings and is a valid context.
        - `tags` are all `planning-<slug>` (closed vocabulary).
        - `related-notes` wikilinks resolve to existing vault notes.

    `related-code` is intentionally NOT checked: notes are historical records
    and the code they point at legitimately moves, renames, and is deleted over
    a note's lifetime (a missing path is normal, not an error), and in a shared
    multi-repo vault a path only resolves from its own checkout. Existence is
    still validated at write time (`new` / `set`) against the local repo.
    `priority` is not checked (features may be untriaged). Body content is not
    scanned (prose slug-mentions would false-positive).

    Args:
        config: Skill configuration.

    Returns:
        Exit code: 0 if all notes pass, 1 if any errors found.
    """
    preflight(config)

    errors: list[str] = []

    for abs_path, fm in iter_all_notes(config):
        relpath = abs_path.relative_to(config.vault_path)

        if not fm:
            errors.append(f"{relpath}: missing or unparseable frontmatter")
            continue

        note_type = fm.get("type")
        if note_type not in VALID_TYPES:
            errors.append(f"{relpath}: type={note_type!r} is not a valid type")
            continue

        note_repo = fm.get("repo")
        repo_areas: tuple[str, ...] | None = None
        if note_repo is None or note_repo == "":
            errors.append(f"{relpath}: repo is missing")
        elif note_repo not in config.repos_map:
            errors.append(
                f"{relpath}: repo={note_repo!r} not admitted "
                f"(known: {sorted(config.repos_map)})"
            )
        else:
            repo_areas = config.repos_map[note_repo]

        area = fm.get("area")
        if area is None or area == "":
            errors.append(f"{relpath}: area is missing")
        elif repo_areas is not None and area not in repo_areas:
            errors.append(
                f"{relpath}: area={area!r} not in repo {note_repo!r} areas "
                f"{sorted(repo_areas)}"
            )

        if note_type != "retro":
            status_val = fm.get("status")
            if status_val is None:
                errors.append(f"{relpath}: status is missing")
            else:
                allowed = STATUS_BY_TYPE.get(note_type, ())  # type: ignore[arg-type]
                if status_val not in allowed:
                    errors.append(
                        f"{relpath}: status={status_val!r} not in {list(allowed)} "
                        f"for type={note_type}"
                    )

        if note_type == "finding":
            sev = fm.get("severity")
            if sev is None:
                errors.append(f"{relpath}: severity is required for findings")
            elif sev not in VALID_SEVERITIES:
                errors.append(
                    f"{relpath}: severity={sev!r} not in {list(VALID_SEVERITIES)}"
                )

            kind = fm.get("kind")
            if kind is None:
                errors.append(f"{relpath}: kind is required for findings")
            elif kind not in VALID_KINDS:
                errors.append(f"{relpath}: kind={kind!r} not in {list(VALID_KINDS)}")

            di = fm.get("discovered-in")
            if di is None or di == "":
                errors.append(f"{relpath}: discovered-in is required for findings")
            else:
                try:
                    validate_discovered_in(str(di))
                except ValidationError as exc:
                    errors.append(f"{relpath}: {exc}")

        related_notes = fm.get("related-notes") or []
        if isinstance(related_notes, list) and related_notes:
            try:
                validate_wikilinks(config, [str(x) for x in related_notes])
            except ValidationError as exc:
                errors.append(f"{relpath}: {exc}")

        tags = fm.get("tags") or []
        if isinstance(tags, list) and tags:
            try:
                validate_tags([str(x) for x in tags])
            except ValidationError as exc:
                errors.append(f"{relpath}: {exc}")

    for line in errors:
        print(line)

    if errors:
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK (all notes pass)")
    return 0


# -----------------------------------------------------------------------------
# Argparse entry point
# -----------------------------------------------------------------------------


def _format_summaries_text(summaries: list[NoteSummary]) -> str:
    """Format a list of NoteSummary as a text table."""
    if not summaries:
        return "(no notes)"
    lines: list[str] = []
    for s in summaries:
        parts = [f"{s.note_type}/{s.slug}"]
        if s.status:
            parts.append(f"[{s.status}]")
        if s.repo:
            parts.append(f"repo={s.repo}")
        if s.area:
            parts.append(f"area={s.area}")
        if s.forward:
            parts.append("forward")
        if s.severity:
            parts.append(f"severity={s.severity}")
        if s.kind:
            parts.append(f"kind={s.kind}")
        if s.discovered_in:
            parts.append(f"discovered-in={s.discovered_in}")
        if s.priority:
            parts.append(f"priority={s.priority}")
        parts.append(f'"{s.title}"')
        lines.append("  ".join(parts))
    return "\n".join(lines)


def _format_summaries_json(summaries: list[NoteSummary]) -> str:
    """Format a list of NoteSummary as JSON."""
    items = []
    for s in summaries:
        items.append(
            {
                "slug": s.slug,
                "path": str(s.path),
                "type": s.note_type,
                "status": s.status,
                "repo": s.repo,
                "area": s.area,
                "title": s.title,
                "severity": s.severity,
                "kind": s.kind,
                "discovered-in": s.discovered_in,
                "batch": s.batch,
                "forward": s.forward,
                "priority": s.priority,
                "created": s.created.isoformat(),
                "updated": s.updated.isoformat(),
                "tags": list(s.tags),
            }
        )
    return json.dumps(items, indent=2)


def main(argv: list[str] | None) -> int:
    """CLI entry point.

    Parses argv into a (command, options) pair and dispatches to the
    corresponding `cmd_*` function. Catches NoteSkillError subclasses and
    prints a concise message to stderr with the appropriate exit code:

        - 0: success
        - 2: ValidationError
        - 3: SlugResolutionError
        - 4: PreflightError
        - 5: ConfigError
        - 1: any other failure

    Args:
        argv: Argument list (excluding program name); None means use sys.argv.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(
        description="note skill — Obsidian-backed tracker",
        prog="cli.py",
    )
    parser.add_argument(
        "--vault", help="Override the vault name (else NOTE_VAULT / repo binding)"
    )
    parser.add_argument(
        "--vault-path", help="Override the vault path (bypasses the machine registry)"
    )
    parser.add_argument(
        "--repo", help="Override the repo name (else the repo binding)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- new ---
    new_parser = subparsers.add_parser("new", help="Create a new note")
    new_parser.add_argument("type", choices=list(VALID_TYPES), help="Note type")
    new_parser.add_argument("title", help="Note title")
    new_parser.add_argument(
        "--severity",
        choices=list(VALID_SEVERITIES),
        help="Severity (required for findings)",
    )
    new_parser.add_argument(
        "--kind",
        choices=list(VALID_KINDS),
        help="Kind (required for findings)",
    )
    new_parser.add_argument(
        "--priority", choices=list(VALID_PRIORITIES), help="Priority (features)"
    )
    new_parser.add_argument(
        "--area",
        required=True,
        help="Package area (required; validated against the vault vocabulary)",
    )
    new_parser.add_argument(
        "--code", nargs="+", dest="related_code", help="Related code paths"
    )
    new_parser.add_argument(
        "--notes", nargs="+", dest="related_notes", help="Related wikilinks"
    )
    new_parser.add_argument("--tags", nargs="+", help="Tags")
    new_parser.add_argument("--body", help="Initial body content")
    new_parser.add_argument("--sprint", help="Sprint path (retros)")
    new_parser.add_argument("--sprint-end", help="Sprint end date ISO (retros)")
    new_parser.add_argument("--decided-on", help="Decision date ISO (decisions)")
    new_parser.add_argument("--sources", nargs="+", help="URLs (research)")
    new_parser.add_argument(
        "--blocking", action="store_true", default=None, help="Blocking (questions)"
    )
    new_parser.add_argument(
        "--discovered-in",
        choices=list(VALID_DISCOVERED_IN_CONTEXTS),
        help="How it surfaced (context; required for findings)",
    )
    new_parser.add_argument(
        "--batch", help="Free grouping slug for a finding (e.g. sprint/round/topic)"
    )
    new_parser.add_argument(
        "--forward",
        action="store_true",
        help="Mark as a forward note (resolves when its area ships)",
    )
    new_parser.add_argument(
        "--no-open", action="store_true", help="Skip opening in GUI"
    )

    # --- status ---
    status_parser = subparsers.add_parser("status", help="Flip note status")
    status_parser.add_argument("slug", help="Note slug or prefix")
    status_parser.add_argument("new_status", help="New status")
    status_parser.add_argument("--reason", help="Optional reason")

    # --- set ---
    set_parser = subparsers.add_parser("set", help="Update a frontmatter field")
    set_parser.add_argument("slug", help="Note slug or prefix")
    set_parser.add_argument("field", help="Field name")
    set_parser.add_argument(
        "value",
        nargs="+",
        help="New value(s). Scalar fields require one; list fields accept many.",
    )

    # --- list ---
    list_parser = subparsers.add_parser("list", help="List notes")
    list_parser.add_argument("--type", dest="note_type", choices=list(VALID_TYPES))
    list_parser.add_argument("--status", help="Status filter; 'all' lists every status")
    list_parser.add_argument("--area")
    list_parser.add_argument("--needs-triage", action="store_true")
    list_parser.add_argument(
        "--tags",
        nargs="+",
        default=None,
        help="Filter to notes containing ALL listed tags (AND semantics)",
    )
    list_parser.add_argument(
        "--kind", choices=list(VALID_KINDS), help="Filter findings by kind"
    )
    list_parser.add_argument(
        "--discovered-in", help="Filter findings by discovered-in context"
    )
    list_parser.add_argument("--repo", dest="list_repo", help="Filter by repo")
    list_parser.add_argument(
        "--forward", action="store_true", help="Only forward notes"
    )
    list_parser.add_argument("--format", choices=["text", "json"], default="text")

    # --- path ---
    path_parser = subparsers.add_parser(
        "path", help="Print absolute filesystem path of a note (resolves slug)"
    )
    path_parser.add_argument("slug", help="Note slug or prefix")

    # --- search ---
    search_parser = subparsers.add_parser("search", help="Search vault")
    search_parser.add_argument("query", help="Search query")

    # --- moc ---
    moc_parser = subparsers.add_parser("moc", help="Run a Bases view query")
    moc_parser.add_argument("name", help="View name")
    moc_parser.add_argument("--format", choices=["json", "md"], default="json")

    # --- open ---
    open_parser = subparsers.add_parser("open", help="Open note in Obsidian GUI")
    open_parser.add_argument("slug", help="Note slug or prefix")

    # --- check ---
    subparsers.add_parser("check", help="Run pre-flight check")

    # --- tags ---
    tags_parser = subparsers.add_parser(
        "tags", help="Aggregate tag usage across all vault notes"
    )
    tags_parser.add_argument("--format", choices=["text", "json"], default="text")

    # --- lint ---
    subparsers.add_parser(
        "lint", help="Validate every note's frontmatter against the schema"
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        config = load_config(
            vault_override=args.vault,
            vault_path_override=args.vault_path,
            repo_override=args.repo,
        )

        if args.command == "new":
            sprint_end: date | None = None
            if args.sprint_end is not None:
                sprint_end = date.fromisoformat(args.sprint_end)

            decided_on: date | None = None
            if args.decided_on is not None:
                decided_on = date.fromisoformat(args.decided_on)

            blocking: bool | None = None
            if args.blocking:
                blocking = True

            spec = NewNoteSpec(
                note_type=args.type,  # type: ignore[arg-type]
                title=args.title,
                repo=config.repo,
                area=args.area,
                severity=args.severity,  # type: ignore[arg-type]
                kind=args.kind,
                priority=args.priority,  # type: ignore[arg-type]
                related_code=args.related_code or [],
                related_notes=args.related_notes or [],
                tags=args.tags or [],
                body=args.body,
                sprint=args.sprint,
                sprint_end=sprint_end,
                decided_on=decided_on,
                sources=args.sources or [],
                blocking=blocking,
                discovered_in=args.discovered_in,
                batch=args.batch,
                forward=args.forward,
            )
            vault_relpath = cmd_new(config, spec, no_open=args.no_open)
            print(f"Created {vault_relpath}")

        elif args.command == "status":
            cmd_status(config, args.slug, args.new_status, args.reason)
            print(f"Status updated: {args.slug} → {args.new_status}")

        elif args.command == "set":
            cmd_set(config, args.slug, args.field, args.value)
            display = " ".join(args.value) if len(args.value) > 1 else args.value[0]
            print(f"Set {args.field}={display} on {args.slug}")

        elif args.command == "list":
            summaries = cmd_list(
                config,
                note_type=args.note_type,  # type: ignore[arg-type]
                status=args.status,
                area=args.area,
                needs_triage=args.needs_triage,
                tags=args.tags,
                kind=args.kind,
                discovered_in=args.discovered_in,
                repo=args.list_repo,
                forward=args.forward,
            )
            if args.format == "json":
                print(_format_summaries_json(summaries))
            else:
                print(_format_summaries_text(summaries))

        elif args.command == "path":
            cmd_path(config, args.slug)

        elif args.command == "search":
            results = cmd_search(config, args.query)
            print(results)

        elif args.command == "moc":
            output = cmd_moc(config, args.name, args.format)  # type: ignore[arg-type]
            print(output)

        elif args.command == "open":
            cmd_open(config, args.slug)

        elif args.command == "check":
            cmd_check(config)

        elif args.command == "tags":
            print(cmd_tags(config, args.format))

        elif args.command == "lint":
            return cmd_lint(config)

    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    except SlugResolutionError as exc:
        print(f"slug error: {exc}", file=sys.stderr)
        return 3
    except PreflightError as exc:
        print(f"preflight error: {exc}", file=sys.stderr)
        return 4
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 5
    except NoteSkillError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(None))
