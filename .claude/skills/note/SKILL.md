---
name: note
description: Obsidian vault-backed tracker for findings, features, questions, retros, decisions, and research. Use to record or query a finding (including confirmed bugs), feature, or open question instead of GitHub issues.
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 ~/.claude/skills/note/cli.py *)
---

# Note

Vault-backed tracker for findings, features, questions, retros, decisions, and research. All operations route through `python3 ~/.claude/skills/note/cli.py`, which wraps the Obsidian CLI. The vault is **outside the repo** (OneDrive-synced).

The skill is installed once at `~/.claude/skills/note` (a symlink into this starter repo) and is shared by every repo pointed at the same vault. `repo_root` resolves from git of cwd, so the active repo is inferred — never hardcoded per repo.

## Vault Configuration

| Setting | Source | Default |
|---|---|---|
| Vault name | `OBSIDIAN_VAULT` env var or `vault` in config file | basename of `vault_path` |
| Obsidian CLI path | `OBSIDIAN_CLI` env var or auto-detect | `/mnt/c/Users/<user>/AppData/Local/Programs/Obsidian/Obsidian.com` |
| Repo root | `REPO_ROOT` env var or git of cwd | (from git) |
| Vault path | `OBSIDIAN_VAULT_PATH` env var or `vault_path` in config file | **required — no auto-detect** |

Optional `~/.config/note.json`:
```json
{
  "obsidian_cli": "/mnt/c/Users/<user>/AppData/Local/Programs/Obsidian/Obsidian.com",
  "vault_path": "/mnt/c/Users/<user>/OneDrive/vaults/<VaultName>"
}
```

Do **not** set `repo_root` in the config file. It is per-repo; git of cwd resolves it correctly in every repo, and a stale config value would silently attribute notes to the wrong repo when git detection fails.

## Vault Layout

```
<vault>/
├── Home.md
├── findings/        # type: finding
├── features/        # type: feature
├── questions/       # type: question
├── retros/          # type: retro
├── decisions/       # type: decision
├── research/        # type: research
├── MOCs/            # Bases views — Open Findings, Roadmap, Critical, etc.
└── _templates/      # one per type
```

Filenames: slug only, lowercase, hyphenated (e.g., `state-store-resume-bug.md`). Date and title live in frontmatter.

## Frontmatter Schema

### Core (every note)

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | enum | yes | `finding \| feature \| question \| retro \| decision \| research` — controlled, rejected on bad value |
| `status` | enum | yes | values per-type, see below |
| `created` | date | yes | ISO date, auto-set on creation |
| `updated` | date | yes | ISO date, auto-maintained on every write |
| `area` | enum | no | controlled vocabulary, sourced at runtime from the shared vault's `meta/note-areas.md` (not hardcoded). One value per note; see that file for the current list. |
| `tags` | list | no | free-form |
| `related-notes` | list | no | wikilinks: `"[[other-note]]"` |

### Per-type extensions

| Type | Status values | Extra fields |
|---|---|---|
| `finding` | `open \| resolved \| deferred` | `severity` (req: `critical \| warning \| trivial` — urgency only), `kind` (req: `bug \| nit \| gap \| design` — what the finding *is*), `related-code` (list), `discovered-in` (req: `<context>` or `<context>__<instance>`, context ∈ `qa \| code-review \| other`) |
| `feature` | `proposed \| scheduled \| implemented \| deferred` | `priority` (`p0 \| p1 \| p2`), `depends-on` (wikilinks), `related-code` |
| `question` | `open \| answered` | `blocking` (bool), `answered-by` (wikilink or repo path) |
| `retro` | (no status) | `sprint` (req, repo path), `sprint-end` (req, date) |
| `decision` | `active \| superseded` | `decided-on` (req, date), `alternatives` (text), `supersedes` (wikilink) |
| `research` | `in-progress \| complete \| abandoned` | `sources` (URL list), `conclusion` (text) |

## Validation Rules

1. **`type` must be one of the six controlled values.** Reject otherwise.
2. **`status` must be valid for the note's `type`.** Reject otherwise.
3. **`area` is required at creation and must be one of the controlled values.** No default. Use `--needs-triage` to find legacy notes with an empty `area`.
4. **`severity`, `kind`, and `discovered-in` are required at creation for findings.** No default. `severity` is urgency (`critical \| warning \| trivial`); `kind` is what the finding is (`bug` = code wrong; `nit` = code works, cleanliness; `gap` = missing test coverage or docs; `design` = architectural or process concern). They are orthogonal.
5. **`priority` is optional at creation for features**, set during triage.
5a. **`discovered-in` is required for findings.** The part before the first `__` must be a valid context (`qa \| code-review \| other`); the optional `__<instance>` suffix is a free grouping slug (e.g. `qa__base-layer`, `code-review__tick-roles-mutations`). Records where a finding was surfaced; do not duplicate it as a tag. **Property values use `__` as the domain/topic separator, never `:` — Obsidian renders colon-bearing values as broken links. Colons are rejected at write and flagged by `lint`.**
6. **`related-code` paths must exist under `repo_root` at write time** (file portion, ignoring `::symbol` suffix). Reject on missing path at creation / `set`. Not re-checked by `lint`: paths point outside the vault at code that legitimately moves over a note's lifetime, and in a shared multi-repo vault a path only resolves from its own checkout.
7. **`related-notes` wikilinks must resolve to existing vault notes.** Reject on missing target.
8. **Filename slugs must be unique within their folder.** Disambiguate with `-2`, `-3` suffix on collision.

## Status Transition Behavior

The skill flips status (including terminal transitions). Every transition:

1. Updates `status` property via `obsidian property:set`.
2. Updates `updated` to today.
3. Appends a line to the note's `## Log` section: `- YYYY-MM-DD: <old> → <new> (<reason if given>)`.

If `## Log` is missing, the skill creates it before appending.

## Pre-flight

Every operation calls a pre-flight check first:
- Obsidian CLI binary is reachable.
- `vault_path` exists and is a directory.
- Vault is accessible (`obsidian files vault=<name> ext=md` succeeds).
- No `*Conflicted Copy*` files in the vault (warning, not blocking).

If pre-flight fails, the operation aborts with a clear error.

## Commands

All run via `python3 ~/.claude/skills/note/cli.py <command> [args]`.

### `new <type> "<title>" [options]`

Create a new note. Generates slug, writes frontmatter from per-type template directly to the vault filesystem (atomic write), then opens in Obsidian.

```
python3 ~/.claude/skills/note/cli.py new finding "State store resume bug" \
  --severity critical \
  --kind bug \
  --area substrate \
  --discovered-in code-review__snapshot-resume \
  --code packages/substrate/src/snapshot.py::resume_kernel
```

Options:
- `--area <name>` (**required**, controlled list)
- `--severity {critical|warning|trivial}` (required for findings)
- `--kind {bug|nit|gap|design}` (required for findings)
- `--discovered-in <context>[__<instance>]` (**required for findings**; context ∈ `qa|code-review|other`)
- `--priority {p0|p1|p2}` (features)
- `--code <path> [<path> ...]` (must exist under repo_root)
- `--notes "[[other-note]]" ...` (must resolve in vault)
- `--tags <tag> [<tag> ...]`
- `--body "<text>"` (initial body content; appended after template sections)
- `--no-open` (skip opening in GUI)

Output: `Created finding/state-store-resume-bug.md`

### `status <slug> <new-status> [--reason "<text>"]`

Flip status. Validates transition is legal for the note's type. Appends to `## Log`.

```
python3 ~/.claude/skills/note/cli.py status state-store-resume-bug resolved \
  --reason "fixed in commit abc1234"
```

### `set <slug> <field> <value> [<value> ...]`

Update a single frontmatter field. Validates if the field is controlled (`type`, `status`, `area`, `severity`, `kind`, `priority`, `discovered-in`).

```
python3 ~/.claude/skills/note/cli.py set state-store-resume-bug priority p0
```

**Scalar fields** require exactly one value and are written via the Obsidian CLI so the running GUI arbitrates.

**List fields** (`tags`, `related-notes`, `related-code`, `depends-on`, `sources`) accept one or more values and **replace the existing list in full** (no append). Written via direct atomic filesystem rewrite. `related-notes` and `related-code` are validated before write.

```
python3 ~/.claude/skills/note/cli.py set my-finding related-notes "[[a]]" "[[b]]"
python3 ~/.claude/skills/note/cli.py set my-feature tags forward-note nhs-roadmap
```

`type` cannot be changed via `set` (file would need to move folders). Use `migrate` if it ever exists.

### `list [filters] [--format text|json]`

List notes by filter. Default (no `--status`): non-terminal statuses only — `open`, `active`, `proposed`, `scheduled`, `in-progress`. Terminal-status notes (`resolved`, `deferred`, `answered`, etc.) are hidden unless requested. Uses filesystem scanning — works without Obsidian running.

```
python3 ~/.claude/skills/note/cli.py list --type finding --status open
python3 ~/.claude/skills/note/cli.py list --type finding --status all   # every status
python3 ~/.claude/skills/note/cli.py list --area substrate
python3 ~/.claude/skills/note/cli.py list --needs-triage    # area is empty
```

Options:
- `--type <type>` — filter by type
- `--status <status>` — filter by status (must be valid for filtered type). Pass `all` to list every status, including terminal ones.
- `--area <name>` — filter by area
- `--needs-triage` — notes with empty `area`
- `--tags <tag> [<tag> ...]` — require all listed tags (AND semantics)
- `--kind {bug|nit|gap|design}` — filter findings by kind
- `--discovered-in <slug>` — filter findings by `discovered-in`
- `--format {text|json}` — default `text`

```
python3 ~/.claude/skills/note/cli.py list --tags forward-note --area dialect-tick
python3 ~/.claude/skills/note/cli.py list --type finding --status all --kind nit
```

### `path <slug>`

Print the absolute filesystem path of a note (resolves slug). Use the `Read` tool on the returned path to view contents.

```
python3 ~/.claude/skills/note/cli.py path state-store-resume-bug
# Output: <vault_path>/findings/state-store-resume-bug.md
```

### `search "<query>"`

Full-text vault search. Wraps `obsidian search:context`.

### `moc <name> [--format json|md]`

Run a Bases view query. `<name>` matches a view in any base file under `MOCs/`.

```
python3 ~/.claude/skills/note/cli.py moc "Open Findings" --format json
```

### `open <slug>`

Open a note in Obsidian's GUI.

### `check`

Run pre-flight only. Useful when starting a session. Prints vault, vault_path, repo_root, obsidian_cli.

### `tags [--format text|json]`

Aggregate tag usage across the entire vault. Output is sorted by count descending; ties alphabetical. Use this **before inventing a new tag** to discover existing ones and avoid drift (e.g. `nhs-roadmap` vs `roadmap`).

Tags are free-form and carry **topic** only — `kind`, `severity`, and `discovered-in` are fields, not tags, so don't duplicate them. **Tags use `-` as their only separator and must not contain `:` — colons render as broken tag-pills in Obsidian and are rejected at write and by `lint`.** Roadmap / planning membership uses a namespaced tag: `planning-<slug>` (e.g. `planning-nhs`). The `planning-` prefix self-documents the tag as a planning marker rather than a topic; it is convention, not enforced. Domain/topic grouping that needs a structured separator belongs in the `discovered-in` property (which uses `__`), not in a tag.

```
python3 ~/.claude/skills/note/cli.py tags
# forward-note                24
# nhs-roadmap                  8
# ...
```

### `lint`

Validate every note's frontmatter against the controlled schema. Frontmatter-only — does not scan body prose.

Checks per note: `area` is set and valid, `status` is set and valid for the type, `severity` and `kind` are set and valid for findings, `related-notes` wikilinks resolve. `related-code` is intentionally not checked — it points outside the vault at code that moves over a note's lifetime, and only resolves from its own checkout in a shared multi-repo vault (it is still validated at write time). `priority` is also not checked (features may be untriaged).

Exits 0 if all notes pass, 1 if any errors. Output is one line per error: `<vault-relpath>: <issue>`.

```
python3 ~/.claude/skills/note/cli.py lint
```

Run after touching multiple notes (e.g. a backfill batch) and as part of the post-sprint pruning workflow.

## Slug Resolution

`<slug>` arguments resolve using filesystem glob over `vault_path`:
1. Exact filename match (without `.md`) anywhere in vault.
2. Unique prefix match.
3. Error if ambiguous, listing candidates as vault-relative paths.

Type-folder is auto-detected from the resolved file's location.

## LLM Workflow

### Filing findings during a review

```
python3 ~/.claude/skills/note/cli.py new finding "Title" \
  --severity critical --kind bug --area <pkg> \
  --discovered-in code-review__<sprint-or-topic> --code <path>
```

### Triaging a captured note

```
python3 ~/.claude/skills/note/cli.py set <slug> area <pkg>
python3 ~/.claude/skills/note/cli.py set <slug> priority p1   # if feature
```

### Resolving

```
python3 ~/.claude/skills/note/cli.py status <slug> resolved --reason "fixed in <commit>"
```

### Checking state at session start

```
python3 ~/.claude/skills/note/cli.py check
python3 ~/.claude/skills/note/cli.py list --needs-triage
python3 ~/.claude/skills/note/cli.py moc "Critical" --format json
```

### Discovering tags before inventing a new one

```
python3 ~/.claude/skills/note/cli.py tags
```

### Validating the vault after a batch of edits

```
python3 ~/.claude/skills/note/cli.py lint
```

### Resolving forward-notes when a sprint ships subsystem X

```
python3 ~/.claude/skills/note/cli.py list --tags forward-note --area <X>
# For each result:
python3 ~/.claude/skills/note/cli.py status <slug> complete --reason "..."   # research
python3 ~/.claude/skills/note/cli.py status <slug> answered --reason "..."   # questions
python3 ~/.claude/skills/note/cli.py lint
```

### Reading a note's contents

```
# Get the path first:
python3 ~/.claude/skills/note/cli.py path <slug>
# Then use the Read tool on the returned absolute path.
# Do NOT use `note show` — that subcommand no longer exists.
```

## Implementation Notes

- **Hybrid write model.** The Obsidian CLI has a hard ~5000-char buffer for the `content=` argument. Past that threshold, the launcher process hangs (the running Obsidian process throws a SyntaxError dialog). To avoid this: new-note creation writes directly to the vault filesystem (no contention since the target file does not exist); all writes to existing notes (property sets, log appends) go through the Obsidian CLI so the running GUI arbitrates.
- **30s CLI timeout.** All CLI calls have a 30-second timeout. On expiry, the wrapper kills stuck launcher processes (`pkill -9 -f /init.*Obsidian` and `pkill -9 -f Obsidian.com`) and raises `PreflightError`.

## Principles

- **Vault is outside the repo.** No context pollution during codebase searches.
- **Status drives lifecycle, not folders.** Status flips are property edits, not file moves. Wikilinks survive.
- **Per-type schemas are strict for `type` and `status`.** Loose for everything else.
- **Writes to existing notes go through Obsidian** (via CLI subprocess) so the running GUI arbitrates. New-note creation writes directly to the vault filesystem — no contention is possible since the target file doesn't exist.
- **Repo never references vault.** One-way: vault → repo. If a vault note becomes load-bearing for active code, its content migrates into the repo.
- **MOCs are the source of truth for views.** Skill calls `base:query`; doesn't reimplement filtering.

## Integration with Other Skills

Review skills (`review-sprint`, `arch-review`, etc.) file findings via this skill. Reference notes by slug in summaries (`note: state-store-resume-bug`).
