---
name: arch-design
description: Design architecture docs for new features, refactors, or redesigns. Produces a pending architecture doc describing a specific change — semantics, contracts, invariants. File enumeration happens at sprint planning.
argument-hint: [feature-name or issue path]
---

# Architecture Design

Design a pending architecture doc describing a specific change to the system —
a new feature, a refactor, or a redesign.

The deliverable is an **architecture artifact**, not a sprint precursor. It
defines *what* the change is and *why* — semantics, contracts, invariants,
rationale. It does NOT enumerate files, line ranges, or import rewrites —
those belong to sprint planning.

All pending docs live at `docs/architecture/pending/<name>.md`. There is no
per-package pending location and no `owns` frontmatter; the doc's content —
specifically the `Affected Subsystems` section — describes which subsystems
the change touches.

## Audience (LLM)

Design docs should be optimized for LLM use.

## Inputs

The user provides one of:
- A feature name or concept (e.g., "behavior mutations")
- A path to a feature doc (e.g., a `/note` entry)
- A description of the problem to solve

## Context posture

**Full architecture.** Run `/understand architecture` first — it loads the
pipeline boundaries, `docs/PROCESS.md`, and the `docs/CAPABILITIES.md` outline
that a design has to hold to. Everything below is what this skill loads *on top
of* that bundle; do not re-read what the bundle already gave you.

## Process

### Checkpoint 1: Problem + Solution (wait for user approval)

1. **Load context:**
   - The design index for each subsystem the change touches — under the subsystem-doc location the bundle declared, one `README.md` per subsystem
   - `## Forward constraints introduced` in the architecture docs of the subsystems this design touches — a constraint binding your design lives in the doc that raised it, with its retirement trigger stated inline
   - **Obsidian forward-notes for the area:** `python3 ~/.claude/skills/note/cli.py list --forward --area <package-area>`. Read each result's body and front-matter. `decision` entries are binding — a rule the team settled that your design must hold to. `research`, `feature`, and `question` entries carry hypotheses, scale-roadmap context, and "may change" guidance. **For an unbuilt subsystem that has no package or area yet** `--area` won't match — search `cross-cutting` plus the closest existing related areas.
   - If user provided an issue path, read that too

2. **Write Problem and Solution sections:**
   - Problem: What's wrong or missing. Include a concrete example (config snippet, error, limitation).
   - Solution: High-level approach. One paragraph + diagram or YAML snippet.

3. **Present to user for approval.** Name the subsystems the change touches.
   Design the **whole feature** — a feature that spans three packages is a
   three-package design. If part of the feature is genuinely separable, say so
   explicitly and explain why; don't silently drop it or present a shrunken
   scope as the safe default. Do not continue until the user confirms direction.

### Automated Phase (after direction is approved)

4. **Load relevant architecture docs** per README.md reading order for each affected area. These docs are *read-only context* — they describe today's contracts and invariants so you can design a change that fits. Do not write the design as a diff against them, do not enumerate which sections will be rewritten, and do not describe how they should be updated. The pending doc describes the change to the *system*, not the change to the docs.

5. **Read existing source code** only as needed to understand current contracts and invariants. Use cclsp to inspect specific symbols. Do not enumerate import sites — that is sprint planning.

6. **Write remaining sections** using the template at `.claude/skills/arch-design/template.md`:
   - **Affected Subsystems** — prose naming each subsystem the change touches and how its contract or behavior changes.
   - **What Doesn't Change** — explicit scope boundaries; a fence against scope creep.
   - **Semantics** — behavioral rules, edge cases, ordering, timing; invariants the design relies on and introduces.
   - **Configuration** — YAML examples if the feature has author-facing config.
   - **Interface Contracts** — function signatures with full docstrings.
   - **Validation Rules** — parse-time (Pydantic) and business rules.

7. **Write the complete doc** to `docs/architecture/pending/<name>.md`.

8. **Present the full doc to user** with a summary of:
   - Subsystems affected (named, not enumerated as files)
   - Any design decisions that could go either way (flag for user)

## Quality Rules

- **Must be complete** — every behavior is specified, every contract has Args/Returns/Raises, every invariant the design depends on is stated. Completeness is an architecture property; *implementability* (which files, which imports) is a sprint-planning property and is out of scope here.
- **Design the whole feature, not a slice.** The doc covers everything the feature needs to be usable end-to-end — companion verbs, the reader for a writer, the neighbor interface a new surface depends on. If the feature needs a contract a sibling subsystem lacks, design that contract here as part of the feature. Deferral is legitimate only for genuinely separable sub-features and must be called out as a decision.
- **No file inventories, line ranges, or import-rewrite tables.** If the doc starts naming private helpers to add or line ranges to delete, stop — that belongs in the sprint plan.
- **No invented scenario values** (the no-invented-values principle) — contracts must not introduce defaults for author-specified parameters.
- **No future scaffolding** (the no-future-scaffolding principle) — design only what this feature needs, not extensibility for hypothetical future work.
- **Breaking changes are fine** (the breaking-changes principle) — don't add compatibility shims.
- **Concrete contracts** — every function signature includes Args, Returns, Raises. No `...` bodies in the doc; show the signature and docstring only.
- **Testable semantics** — the Semantics section should use tables (Condition | Result) so sprint specs can derive test cases directly.
- **No implementation code** — design docs contain signatures and docstrings, never implementation bodies. Describe behavior in prose and tables, not code blocks with for-loops or if-statements. Wrong: showing the literal code to insert into `processor.py`. Right: "After `execute_action()` returns non-empty decisions, apply mutations and record history if tracked."
- **The doc never references itself.** It does not list its own path among "affected files" or prescribe its own future pruning.
- **The design talks about the system, not about docs.** Code, contracts, semantics, invariants, and reasoning are the subject. Sibling architecture docs are not — not as edit targets, not as something to be "delta'd against," not as authority citations. If a fact from a sibling doc is load-bearing, state the fact; don't cite the doc. Post-implementation doc maintenance is a separate concern and never appears in the pending doc.

## Output Location

All pending docs: `docs/architecture/pending/<feature-name>.md`.

## Boundary with sprint planning

Architecture design ends at the contract. Sprint planning begins with the contract and produces:
- File inventory (Create/Modify per path)
- Import-rewrite tables for moved or renamed symbols
- Phase breakdown and ordering
- Test file mapping

If you find yourself wanting to write any of the above during `/arch-design`, that's a signal the design is done and a sprint plan should be opened separately.
