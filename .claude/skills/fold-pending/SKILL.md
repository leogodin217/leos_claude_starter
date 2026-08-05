---
name: fold-pending
description: Fold the information in a shipped pending architecture doc into canonical package docs. Use after the sprint that implemented a pending/*.md doc has landed. Verifies delivery, redistributes information by ownership, re-voices and re-structures it into a canonical doc, prunes retired forward constraints and Obsidian notes, deletes the pending file.
argument-hint: [path-to-pending-doc ...]
agent: architect
disable-model-invocation: true
---

# Fold Pending Information

The pending doc was a temporary carrier. Its information now belongs to whichever
canonical docs own those contracts. **Folding transfers information; it does not
promote a file.** The pending file is deleted at the end — nothing "graduates."

This skill runs *after* the sprint that implemented a `pending/*.md` doc has
landed. It is the missing step between `/implement-sprint` and a clean
architecture tree.

## Pending docs vs. canonical docs

Folding is a transformation between two different kinds of document. Knowing the
difference *is* the skill — every phase below serves it.

| | Pending doc (`docs/architecture/pending/*.md`) | Canonical doc (a subsystem doc) |
|---|---|---|
| **Purpose** | A proposal, written once for design review | A permanent contract reference for implementers and adjacent designers |
| **Lifespan** | Temporary carrier — deleted after folding | Lives as long as the code it describes |
| **Owner** | Nobody — a proposal in flight | The subsystem that owns the contract |
| **Voice** | Delta — describes the *change* ("X now does Y", "we rejected W", "Z unchanged") | Steady-state — a plain statement of the current contract, no history |
| **Structure** | Self-contained narrative: Problem, Solution, What Doesn't Change, then the design | Contract sections — Boundary, Invariants, Rationale — matching the package's other docs |
| **Schema / examples** | Spelled out in full — the doc *is* the spec, no code exists yet | Schema and examples become links; the doc keeps reasoning, not restatement |
| **Scope framing** | Sprint-bound — "sprint 1", "out of scope (v1)", scope cuts | None — describes what *is*, not what a sprint did or deferred |

Folding therefore changes three things at once, not one:

1. **Voice** — delta → steady-state.
2. **Structure** — narrative → the contract sections the package's other canonical
   docs use (see `templates/canonical-arch-doc.md`).
3. **Density** — full spec → links for schema and examples, *but* rationale,
   invariants, constraints, and normative algorithms are kept and stated as
   contract. A short doc is fine; a doc thin on *why* is the failure.

The common failure is to treat folding as relocation plus a verb swap — move the
file, delete the "now"s. That leaves a doc with pending *structure* and pending
*density* (schema tables, YAML, sprint-scoping sections) even when every sentence
reads as steady-state. It still reads as a proposal. A reader who never saw the
pending doc — an implementer extending the package, a designer of an adjacent
subsystem — must be able to read every sentence as a plain statement of current
contract.

Two steps are gated and must not be skipped: **verify delivery** (Phase 1) and
**re-voice + re-structure** (Phases 4–5).

## Input

One or more paths to pending docs under `docs/architecture/pending/*.md`. If no
path is given and exactly one pending doc exists, use it; if several exist, list
them and ask which.

All pending docs live at `docs/architecture/pending/<name>.md` — there is no
per-package pending location. Routing into canonical package docs is decided
here in Phase 3 from the doc's `Affected Subsystems` section, not from
frontmatter.

## Context posture

**Full architecture.** Run `/understand architecture` first — it loads the
pipeline boundaries, `docs/PROCESS.md` (which owns the folding rules), and the
`docs/CAPABILITIES.md` outline a fold updates. `CLAUDE.md` is already in
context. On top of the bundle, load:

1. `templates/canonical-arch-doc.md` — the section spine a folded doc targets
2. The pending doc(s) to fold

## Phase 1 — Verify delivery (GATE: hard STOP)

Everything the pending doc claims as shipped must actually exist in code.

- Extract every concrete artifact the doc names: classes, functions, Pydantic
  models, validation rules, `Implementation:` links.
- Confirm each exists — `find_definition` / `find_references` / Grep. Check the
  contract matches (signature, fields, raises) — not just that the name exists.
- Verify every section that asserts code: Semantics, Interface Contracts,
  Validation Rules, Configuration. Older docs may carry a Design Context /
  Architecture zone split — the verification target is the same: anything the
  doc claims as built.

If anything is missing, partial, or contradicts the doc: **STOP. Present the gap
and ask the user how to proceed.** Do not fold a doc whose design was not fully
built.

## Phase 2 — Classify the information

Sort every unit of information into one of:

| Class | Destination |
|---|---|
| **Design-review framing** — What Doesn't Change, the design-review pitch | Dropped. Never folded. |
| **Problem / Solution** | Compressed into the canonical doc's one-paragraph Purpose; load-bearing *why* moves to Rationale. |
| **Routing map** — Affected Subsystems | Not folded; *used* to pick destinations in Phase 3. |
| **Semantics extending an existing subsystem** | Merged into that subsystem's arch doc. |
| **A coherent new contract surface** | Its own new doc, `<name>.md`, under the subsystem-doc location the bundle declared. |
| **Rationale / constraints / invariants / boundaries still load-bearing** | Kept — moved to the owning doc. |
| **Schema / field shapes the code restates** | Dropped — replaced by a link to the model. |
| **Examples** | Dropped — replaced by a link to the tests. |
| **Normative or non-obvious algorithms** | Kept — state the contract; the code is one conformant implementation. |

Classify section by section. `Problem`, `Solution`, `Affected Subsystems`, and
`What Doesn't Change` are design-review framing or routing — they compress into
the canonical Purpose / Rationale or are dropped. `Semantics`, `Configuration`,
`Interface Contracts`, and `Validation Rules` are the contract payload that
gets redistributed.

Two splits decide most units:

- **Problem/Solution is not pure scaffolding.** A canonical doc opens by stating
  what the subsystem is and the problem it solves — tightly, in one paragraph,
  not as a review pitch. Compress, do not delete. Only What Doesn't Change and the
  design-review framing are dropped outright.
- **Schema vs. algorithm** turns on one question: *does the code derive this, or
  must the code conform to it?* A field list the model regenerates is derivable —
  link it. A byte layout, an ordering guarantee, a normative derivation an
  independent reimplementation must honor is a constraint the code conforms to —
  keep it, stated as contract.

## Phase 3 — Decide the split (GATE: present, then confirm)

Using Affected Subsystems as the routing map, decide each unit's destination
doc. The default failure mode is "merge everything into the nearest existing
doc" — resist it. A large pending doc usually **splits**: most sections merge
into existing docs, but a coherent new contract surface is promoted to its own
sibling doc.

Present the split plan as a table — *unit → destination doc → merge or new* —
and wait for the user to confirm before writing anything.

## Phase 4 — Re-voice, re-structure, and distribute (GATE: steady-state voice)

Before writing, fix the **structure**. Open a sibling canonical doc in the
destination package and match its section vocabulary. For a new doc, use the
spine in `templates/canonical-arch-doc.md`. The pending doc's narrative arc
(Problem → Solution → narrative design) does not survive — its content is
re-sorted into the canonical sections (Boundary, Semantics, Invariants,
Rationale, Boundaries). A folded doc that still carries the pending doc's
section headings is a structural fold defect, even if every sentence is
re-voiced.

Then write each kept unit into its destination. **Transform delta voice into
steady-state voice as you write** — this is the step hand-folding skips:

| Delta voice (pending) | Steady-state voice (canon) |
|---|---|
| "The Distribution Protocol *stays* `(rng,params)→Δ`" | "The Distribution Protocol is `(rng,params)→Δ`" |
| "MasterClock *gains no* calendar awareness" | "MasterClock has no calendar awareness" |
| "We *rejected* the per-window timezone" | "Timezone is calendar-level, not per-window — a per-window timezone would make event ordering timezone-dependent" |
| A "What Doesn't Change" bullet | Dropped, or restated as a Boundary if load-bearing |

A reader who never saw the pending doc must read every folded sentence as a plain
statement of current contract. No "now", "stays", "unchanged", "previously",
"rejected", "no longer".

Then update each touched package's `docs/architecture/README.md` reading order
and status table.

## Phase 5 — Voice and structure lint

Grep the destination docs for surviving delta voice:

```bash
grep -niE '\b(now|no longer|stays?|unchanged|rejected|previously|used to|will (now|change))\b' <destination-doc> ...
```

Review every hit. Most "now" hits are innocent ("the calendar now-time") — judge
in context. Any hit that frames a fact as a *change* is a fold defect: rewrite it.

Then check the structure against `templates/canonical-arch-doc.md` and a sibling
canonical doc:

- No pending-only sections survive (`Problem`, `Solution`, `What Doesn't Change`,
  `Affected Subsystems`, `Out of scope (vN)`).
- No sprint-scoping voice — "sprint N", "v1 ships", "deferred to a later sprint".
- Schema tables / YAML / JSON blocks are replaced by links unless the block is a
  normative algorithm kept as contract.
- The doc has a one-paragraph Purpose, not a Problem/Solution pair.

## Phase 6 — Mechanical tail

1. **Retired forward constraints** — in every package arch doc this sprint
   touched, delete each `## Forward constraints introduced` entry whose
   retirement trigger the sprint met. A newly-discovered constraint goes into
   the *owning subsystem's* arch doc, next to the contract it binds.
2. **Obsidian forward-notes** — `python3 ~/.claude/skills/note/cli.py list --forward --area <shipped-area>`.
   For each: `note status <slug> complete` (research; set `conclusion`),
   `note status <slug> answered` (questions; set `answered-by`), or
   `note status <slug> superseded` (decisions).
3. **Delete** the `pending/<name>.md` file(s).
4. `python3 ~/.claude/skills/note/cli.py lint` — catch broken `related-notes`
   wikilinks.
5. Update `docs/CAPABILITIES.md` - Update/add any capabilities that are out of date

## Phase 7 — Summary

Report: docs delivered-verified; per-unit destinations; new docs created;
retired forward constraints pruned; notes resolved; pending files deleted; voice
- and structure-lint hits found and fixed.
