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

`subsystem-docs` is not part of the reading list — it states where *this* repo
keeps per-subsystem architecture docs, so a skill can be written once and run
against repos laid out differently (`packages/*/docs/architecture/` in one,
a flat `docs/architecture/` in another). It is rendered with the bundle, and a
skill whose context posture forbids loading a whole bundle can read it alone:

    load.py <project> --field subsystem-docs

Declare it in one bundle only. It is a repo-level fact, and a second copy is a
second thing to keep true.

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
