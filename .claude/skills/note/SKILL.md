---
name: note
description: Obsidian vault-backed tracker for findings, features, questions, retros, decisions, research, and plans. Use to record or query a finding (including confirmed bugs), feature, open question, or cross-repo plan instead of GitHub issues.
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 ~/.claude/skills/note/cli.py *)
---

# Note

Vault-backed tracker for findings, features, questions, retros, decisions, research, and plans. All operations route through `python3 ~/.claude/skills/note/cli.py`, which wraps the Obsidian CLI. The vault is **outside the repo** (Obsidian Sync).

The skill is installed once at `~/.claude/skills/note` (a symlink into this starter repo) and is shared by every repo pointed at the same vault. One shared vault can serve several related repos; each note is stamped with the `repo` it was created in.

## Vault Configuration — the three-layer binding

Three layers agree before any operation. This is what lets one vault serve several repos while keeping unrelated repos out.

| Layer | Lives in | Owned by | Declares |
|---|---|---|---|
| **Repo binding** | `<repo>/.claude/note.json` (committed) | the repo | logical vault name + this repo's name in it |
| **Machine registry** | `~/.config/note.json` (laptop-local) | the machine | vault name → absolute path on this disk |
| **Vault registry** | `<vault>/meta/note-areas.md` (synced) | the vault | which repos are admitted + each repo's area list |

Repo binding — committed, portable (no absolute paths):
```json
{ "vault": "Fabulexa", "repo": "composite" }
```

Machine registry `~/.config/note.json`:
```json
{
  "obsidian_cli": "/mnt/c/Users/<user>/AppData/Local/Programs/Obsidian/Obsidian.com",
  "vaults": { "Fabulexa": "/mnt/c/Users/<user>/obsidian/Fabulexa" }
}
```

**Four fail-closed gates** (no default vault — an unbound repo cannot write notes):

1. **UNBOUND** — no vault name from `--vault`, `NOTE_VAULT`, or the repo binding.
2. **VAULT-UNKNOWN** — vault name not in the machine `vaults:` map.
3. **REPO-UNREGISTERED** — repo name not a key in the vault `repos:` map.
4. **AREA-INVALID** — at write time, `area` not in the current repo's area list.

**Membership is a two-key handshake:** a repo is operational only when it *both* declares a binding *and* is registered in the vault's `repos:` map. Overrides `--vault` / `--vault-path` / `--repo` and `NOTE_VAULT` sit above the binding in precedence for reaching a second vault without editing committed state.

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
├── plans/           # type: plan
├── MOCs/            # Bases views — Open Findings, Roadmap, Critical, etc.
└── _templates/      # one per type
```

Filenames: slug only, lowercase, hyphenated (e.g., `state-store-resume-bug.md`). Date and title live in frontmatter.

## Frontmatter Schema

### Core (every note)

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | enum | yes | `finding \| feature \| question \| retro \| decision \| research \| plan` — controlled, immutable |
| `status` | enum | yes | values per-type, see below |
| `created` | date | yes | ISO date, auto-set on creation |
| `updated` | date | yes | ISO date, auto-maintained on every write |
| `repo` | enum | yes | which repo owns the note. **Stamped from the binding at creation, never author-typed, immutable.** A key in the vault `repos:` map. Plans additionally carry a `repos` list (see below) — the scalar `repo` is unchanged and still stamped/immutable. |
| `area` | enum | yes* | sub-package **within `repo`**, validated against that repo's list in `meta/note-areas.md`. `cross-cutting` = cross-package within one repo. *Not valid on `plan` — plans have no `area` (they coordinate `repos` instead). |
| `forward` | bool | no | `true` marks a forward note (resolves when its area ships). Filter with `list --forward`. |
| `tags` | list | no | **closed vocabulary: only `planning-<slug>`** (workstream/roadmap membership). Every other tag is rejected. |
| `related-notes` | list | no | wikilinks: `"[[other-note]]"` (resolve vault-wide, so cross-repo links are legal) |

### Per-type extensions

| Type | Status values | Extra fields |
|---|---|---|
| `finding` | `open \| resolved \| deferred` | `severity` (req: `critical \| warning \| trivial` — urgency), `kind` (req: `bug \| nit \| gap \| design` — what it *is*), `discovered-in` (req: controlled context, below), `batch` (free slug), `related-code` (list) |
| `feature` | `proposed \| scheduled \| implemented \| deferred` | `priority` (`p0 \| p1 \| p2`), `depends-on` (wikilinks), `related-code` |
| `question` | `open \| answered` | `blocking` (bool), `answered-by` (wikilink or repo path) |
| `retro` | (no status) | `sprint` (req, repo path), `sprint-end` (req, date) |
| `decision` | `active \| superseded` | `decided-on` (req, date), `alternatives` (text), `supersedes` (wikilink) |
| `research` | `in-progress \| complete \| abandoned` | `sources` (URL list), `conclusion` (text) |
| `plan` | `active \| complete \| wont-do` | `repos` (req, list of registered repos — the repos this plan coordinates, author order preserved). No `area`. |

**`discovered-in` + `batch` (findings).** `discovered-in` is a controlled *context* — how the finding surfaced: `qa \| code-review \| arch-design \| arch-review \| planning \| other`. `batch` is a free grouping slug (sprint / round / topic, e.g. `snapshot-resume`, `nhs-perf`). They were one composite `context__instance` field; now split so each half is queryable.

**Provenance vs lifecycle.** `type`, `repo`, `area`, `created`, `discovered-in`/`batch` are immutable provenance (set once). Only `status`/`updated` and terminal fields change over a note's life.

## Validation Rules

1. **`type` must be one of the seven controlled values.** Immutable — `set type` and `set repo` are rejected (both are provenance; `type` would need a folder move).
2. **`status` must be valid for the note's `type`.** Reject otherwise.
3. **`repo` is stamped from the binding, not author-supplied.** It must be a key in the vault `repos:` map (else REPO-UNREGISTERED at config time). Immutable after creation.
4. **`area` is required and must be in the note's `repo` area list — except for `plan`, which has no `area`.** No default. `cross-cutting` means cross-package within one repo. `lint` validates each note's area against *its own* repo's list; a `plan` that has an `area` set is a lint error.
5. **`repos` is required (>=1 entry) for `plan`, rejected for every other type.** Each entry must be a key in the vault `repos:` map (else the error names `meta/note-areas.md`); duplicates are rejected. Author order is preserved — not sorted, not deduped. Mutable via `set <slug> repos a b c` (full-replacement, re-validated) since a plan's span may grow.
6. **`severity`, `kind`, and `discovered-in` are required at creation for findings.** `severity` is urgency (`critical \| warning \| trivial`); `kind` is what the finding is (`bug` = code wrong; `nit` = cleanliness; `gap` = missing coverage/docs; `design` = architectural/process); orthogonal. `discovered-in` must be a controlled context (`qa \| code-review \| arch-design \| arch-review \| planning \| other`) — validated at write **and** by `lint`. Put any grouping slug in `batch` (free; no `:`).
7. **`tags` are a closed vocabulary — only `planning-<slug>`.** Any other tag is rejected at write and by `lint`. Topic → `area`/`repo`; how it surfaced → `discovered-in`; finding kind → `kind`.
8. **`priority` is optional at creation for features**, set during triage.
9. **`related-code` paths must exist under the checkout at write time** (file portion, ignoring `::symbol`). Reject on missing path at creation / `set`. **Not checked by `lint`**: notes are historical records and the code they point at legitimately moves; in a shared multi-repo vault a path only resolves from its own checkout.
10. **`related-notes` wikilinks must resolve to existing vault notes** (vault-wide, so cross-repo links are legal). Reject on missing target.
11. **Filename slugs must be unique within their folder.** Disambiguate with `-2`, `-3` suffix on collision.

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

`repo` is stamped automatically from the binding — you never pass it.

```
python3 ~/.claude/skills/note/cli.py new finding "State store resume bug" \
  --severity critical \
  --kind bug \
  --area substrate \
  --discovered-in code-review \
  --batch snapshot-resume \
  --code packages/substrate/src/snapshot.py::resume_kernel
```

Options:
- `--area <name>` (**required for every type except `plan`**, must be in this repo's area list; **rejected** for `plan`)
- `--repos <name> [<name> ...]` (**required for `plan`**, each a registered repo; **rejected** for every other type)
- `--severity {critical|warning|trivial}` (required for findings)
- `--kind {bug|nit|gap|design}` (required for findings)
- `--discovered-in {qa|code-review|arch-design|arch-review|planning|other}` (**required for findings**)
- `--batch <slug>` (findings; free grouping slug — sprint/round/topic)
- `--forward` (mark as a forward note)
- `--priority {p0|p1|p2}` (features)
- `--code <path> [<path> ...]` (must exist under the current checkout)
- `--notes "[[other-note]]" ...` (must resolve in vault)
- `--tags planning-<slug> [...]` (only `planning-*` tags are accepted)
- `--body "<text>"` (initial body content; appended after template sections)
- `--no-open` (skip opening in GUI)

Top-level overrides (before the subcommand): `--vault <name>`, `--vault-path <path>`, `--repo <name>` for reaching a second vault or repo without editing committed state.

Output: `Created findings/state-store-resume-bug.md`

### `status <slug> <new-status> [--reason "<text>"]`

Flip status. Validates transition is legal for the note's type. Appends to `## Log`.

```
python3 ~/.claude/skills/note/cli.py status state-store-resume-bug resolved \
  --reason "fixed in commit abc1234"
```

### `set <slug> <field> <value> [<value> ...]`

Update a single frontmatter field. Validates if the field is controlled (`status`, `area`, `severity`, `kind`, `priority`, `discovered-in`, `batch`, `tags`).

```
python3 ~/.claude/skills/note/cli.py set state-store-resume-bug priority p0
```

**Scalar fields** require exactly one value and are written via the Obsidian CLI so the running GUI arbitrates. `area` is validated against the note's *own* repo's area list; rejected outright on `plan` notes (no `area`). `forward` and `blocking` are boolean.

**List fields** (`tags`, `related-notes`, `related-code`, `depends-on`, `sources`, `repos`) accept one or more values and **replace the existing list in full** (no append). Written via direct atomic filesystem rewrite. `tags` (must be `planning-*`), `related-notes`, `related-code`, and `repos` (only settable on `plan` notes, re-validated against the vault registry) are validated before write.

```
python3 ~/.claude/skills/note/cli.py set my-finding related-notes "[[a]]" "[[b]]"
python3 ~/.claude/skills/note/cli.py set my-feature tags planning-nhs
```

`type` and `repo` cannot be changed via `set` — both are immutable provenance (`type` would need a folder move; `repo` is stamped at creation).

### `list [filters] [--format text|json]`

List notes by filter. Default (no `--status`): non-terminal statuses only — `open`, `active`, `proposed`, `scheduled`, `in-progress`. Terminal-status notes (`resolved`, `deferred`, `answered`, etc.) are hidden unless requested. Uses filesystem scanning — works without Obsidian running.

```
python3 ~/.claude/skills/note/cli.py list --type finding --status open
python3 ~/.claude/skills/note/cli.py list --type finding --status all   # every status
python3 ~/.claude/skills/note/cli.py list --repo forge
python3 ~/.claude/skills/note/cli.py list --needs-triage    # area is empty
```

Options:
- `--type <type>` — filter by type
- `--status <status>` — filter by status (must be valid for filtered type). Pass `all` to list every status, including terminal ones.
- `--repo <name>` — filter by owning repo. Matches when the note's scalar `repo` equals the value **OR** the value appears in a `plan`'s `repos` list (one uniform OR rule; `repos` is empty on non-plan types, so their matching is unchanged).
- `--area <name>` — filter by area
- `--forward` — only forward notes
- `--needs-triage` — notes with empty `area`. `plan` notes have no `area` by design and are excluded from this filter, not swept in as permanently untriaged.
- `--tags planning-<slug> [...]` — require all listed tags (AND semantics)
- `--kind {bug|nit|gap|design}` — filter findings by kind
- `--discovered-in {qa|code-review|arch-design|arch-review|planning|other}` — filter findings by context
- `--format {text|json}` — default `text`

```
python3 ~/.claude/skills/note/cli.py list --forward --area dialect-tick
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

Run pre-flight only. Useful when starting a session. Prints vault, vault_path, repo, repo_root, obsidian_cli — and surfaces the UNBOUND / VAULT-UNKNOWN / REPO-UNREGISTERED gates if the binding is missing or wrong.

### `tags [--format text|json]`

Aggregate tag usage across the entire vault. Sorted by count descending; ties alphabetical.

Tags are a **closed vocabulary — only `planning-<slug>`** (workstream / roadmap membership, e.g. `planning-nhs`). This is the one facet no single-valued field can express. Everything a tag used to carry now lives in a field: topic → `area`/`repo`, how a finding surfaced → `discovered-in`, finding kind → `kind`. Any non-`planning-*` tag is rejected at write and by `lint`.

```
python3 ~/.claude/skills/note/cli.py tags
# planning-nhs                38
# planning-tales               1
```

### `lint`

Validate every note's frontmatter against the controlled schema. Frontmatter-only — does not scan body prose.

Checks per note: `repo` is set and admitted; `area` is set and in the note's **own repo's** area list; `status` is set and valid for the type; `severity`/`kind`/`discovered-in` set and valid for findings; `tags` are all `planning-*`; `related-notes` wikilinks resolve. `related-code` is intentionally not checked — notes are historical records and the code they point at moves; it only resolves from its own checkout anyway (still validated at write time). `priority` is not checked (features may be untriaged).

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
  --discovered-in code-review --batch <sprint-or-topic> --code <path>
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

### Validating the vault after a batch of edits

```
python3 ~/.claude/skills/note/cli.py lint
```

### Resolving forward notes when a sprint ships subsystem X

```
python3 ~/.claude/skills/note/cli.py list --forward --area <X>
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
- **Provenance is immutable; lifecycle mutates.** `type`, `repo`, `area`, `created` are set once and controlled; only `status`/`updated` change over a note's life.
- **Fail closed on binding.** No default vault. An unbound or unregistered repo cannot write notes — membership is the two-key handshake (repo binding + vault registration).
- **Writes to existing notes go through Obsidian** (via CLI subprocess) so the running GUI arbitrates. New-note creation writes directly to the vault filesystem — no contention is possible since the target file doesn't exist.
- **The repo names its vault, but holds no vault content.** The binding (`.claude/note.json`) is a routing pointer only. Content flow stays one-way vault → repo; if a vault note becomes load-bearing for active code, its content migrates into the repo.
- **MOCs are the source of truth for views.** Skill calls `base:query`; doesn't reimplement filtering.

## Integration with Other Skills

Review skills (`review-sprint`, `arch-review`, etc.) file findings via this skill. Reference notes by slug in summaries (`note: state-store-resume-bug`).
