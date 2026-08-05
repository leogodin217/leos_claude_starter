---
name: <area>
description: <one line — shown when /understand is invoked with no argument>
subsystem-docs: <glob — where per-subsystem architecture docs live in this repo>
context: |
  docs/SOME_DOC.md
  docs/architecture/README.md
  docs/BIG_REFERENCE.md   outline  #overview #invariants
---

Prose that orients someone working in this area and lives nowhere else: where
this repo keeps things, which conventions apply, which tools to reach for.

Do not restate what another document or skill already says — point at it. A
bundle that summarises its own sources becomes a fourth copy to maintain.

## Repo-shape keys

Shape keys are not part of the reading list. They state facts about *this* repo
so a shared skill can be written once and run against repos built differently.

| Key | Value | Example |
|---|---|---|
| `subsystem-docs` | Directory glob — where per-subsystem architecture docs live. **Must name a directory, not a file.** | `packages/*/docs/architecture/` |
| `layout` | `monorepo` or `single-package` | `monorepo` |
| `packages` | Directory glob for the packages. Required under `monorepo`, rejected under `single-package`. | `packages/*/` |
| `typecheck-hook` | Name of the repo-wide type-check pre-commit hook | `mypy (strict, all packages)` |
| `output-judge-agent` | Agent that judges generated output. Must exist at `.claude/agents/<name>.md`. | `data-analyst` |

Declare each **in one bundle only** — a repo-level fact stated twice is two
things to keep true, which is what shape keys exist to remove. `--check`
rejects a duplicate even when the values agree.

Two ways to read one. It renders above the bundle body, so a skill that loads
`/understand` already has it; and a skill whose context posture forbids loading
a whole bundle reads it alone:

    load.py <project> --field layout

**These are prompts, not programs.** "Configuring" a skill with a shape key
means the skill body names both branches in its own prose and keys them to the
declared value — *if `layout` is `monorepo`, split phases on package
boundaries; if `single-package`, split on work-shape only*. There is no
templating and no substitution.

`layout` and `packages` are separate on purpose. `layout` decides *which prose
applies* and every consumer reads it; `packages` supplies *a path* and only the
worktree bootstrap needs it. Inferring the boolean from the glob's absence
would make an omission indistinguishable from a misconfiguration.

Adding a key is a commitment every adopting repo must keep. Add one only when a
skill body would otherwise have to assume a layout.

## Writing the `context:` block

One document per line. Bare path = load the whole file. Two modifiers:

- `outline` — emit the heading map instead of the body. Use it for reference
  documents you consult per-section, not read front to back.
- `#anchor` — pin one section. The anchor is the heading lowercased with every
  run of non-alphanumerics replaced by `-`: `## Status legend` → `#status-legend`.
  A pinned section brings its subsections with it. Combine with `outline` to pin
  the framing and map the rest.

Prefer anchors to `N-M` line ranges. Line ranges still work — the fallback for a
document with no usable headings — but they break silently when the file shifts,
whereas a renamed heading fails loudly. Run `load.py <project> --check` to
resolve every selector in every bundle; wire it to a pre-commit hook.

If a document only becomes useful when sliced, that is worth noticing: it is
probably two documents with different read patterns sharing one file.
