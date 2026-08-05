---
name: create-sprint
description: Guide sprint planning from scope assessment to spec artifacts.
disable-model-invocation: true
---

# Plan Sprint

This command guides the sprint planning process.

## Sprint Identity

Every sprint has a kebab-case **name** (e.g. `fork-spec`, `cli-v1`). The name is set during scope approval (Step 2) and is used as:

- The directory: `docs/sprints/<sprint-name>/`
- The future sprint branch: `sprint/<sprint-name>` (created by `/implement-sprint`)
- The future worktree: `../worktrees/<sprint-name>` (created by `/implement-sprint`)

**Validate the name before writing artifacts:**

```bash
# Refuse if any of these collide:
test -d "docs/sprints/<sprint-name>"            # directory exists at HEAD
git show-ref --quiet "refs/heads/sprint/<sprint-name>"   # branch exists
git worktree list | grep -q "worktrees/<sprint-name>"    # worktree exists
```

If any collide, propose a different name (e.g. `<name>-v2`).

## Parent Branch

The sprint commits land on a **parent branch** that is captured at create time. Pick the parent like this:

| Current branch | Parent branch | Action |
|---|---|---|
| `main` or `master` | `<sprint-name>-work` | Auto-create the work branch and switch to it before committing the sprint dir. Tell the user. |
| Anything else | The current branch | No action — sprint will commit there |

Record the choice in `state.yaml:parent_branch`. Step 10 reads this to fork the worktree from the right base, and `/implement-sprint` reads it to confirm the worktree's lineage.

## Conventions

- `<src-tree>` / `<test-tree>` — the source and test directories of the thing
  being changed. Under `layout: monorepo` that is `<packages>/<pkg>/src` and
  `<packages>/<pkg>/tests`; under `layout: single-package` it is `src` and
  `tests`. Substitute the real paths when emitting artifacts — the templates
  below use the placeholders so the same spec shape works in either repo.

## Context posture

**Full architecture.** Run `/understand architecture` first — it loads the
pipeline boundaries a sprint must not cross and the `docs/CAPABILITIES.md`
outline that Step 1 assesses against. `CLAUDE.md` is already in context. Step 3
loads per-package design on top of the bundle, once scope is approved.

## Process

### 1. Assess Current State

From the bundle, read `docs/CAPABILITIES.md` (status per capability) and
`docs/architecture/README.md` § Status (implementation state by module).

Identify gaps: What capabilities are not started or partial?

### 2. Propose Sprint Scope

Based on gaps and dependencies, propose what this sprint should deliver.

**Scope can be:**
- Part of one capability (a single mechanism, not its whole surface)
- Parts of multiple capabilities that are only useful together
- Infrastructure that unblocks a capability (config parsing before anything that reads config)

Write a scope proposal:
```markdown
## Proposed Scope

**Delivers:** [What this sprint produces]

**Capabilities touched:**
- <capability>: <the slice this sprint delivers> (not <the slice it defers>)
- <capability>: <the slice this sprint delivers>

**Rationale:** [Why this scope makes sense—dependencies, complexity, coherence]

**Not included:** [What's explicitly deferred]
```

Present scope to user for approval before proceeding.

### 3. Load Detailed Context

Once scope is approved, load relevant docs:
- `docs/architecture/README.md` - See reading order for which docs to load
- Subsystem design rationale and constraints, under the subsystem-doc location the bundle declared
- `docs/architecture/pending/*.md` - Pending design doc for this feature (if one exists). There is no per-subsystem pending location

If a design doc exists in `pending/`, extract contracts from it. The design doc provides rationale and semantics (the WHY). The sprint spec provides contracts, phases, and test cases (the WHAT). Do not duplicate prose from the design doc — reference it.

### 4. Define Purpose and Success Criteria

Write a clear purpose statement:
- One sentence describing what this sprint delivers
- How an author will use this capability
- Observable success criteria

### 5. Design Contracts

Use the **architect** agent to design interface contracts.

Each contract needs:
- Full function signature with type hints
- Complete docstring (Args, Returns, Raises)
- NO default parameters (the no-invented-values principle)
- NO scaffolding for future work (the no-future-scaffolding principle)
- All error conditions documented
- NO implementation code — signatures and docstrings only

```python
def function_name(
    param1: Type1,
    param2: Type2,
) -> ReturnType:
    """
    One-line summary.

    Args:
        param1: Description
        param2: Description

    Returns:
        Description

    Raises:
        ValueError: When X
    """
    ...
```

For modified functions, describe behavioral changes in the docstring. Do not show implementation diffs (for-loops, if-blocks, code to insert). The implementer writes the code; the contract says what the code should do.

**Anti-scaffolding checklist:**
- [ ] No `# Future:` comments in contracts
- [ ] No methods that will "do nothing for now"
- [ ] No precomputed data that won't be used this sprint
- [ ] Every loop body has real work (no `pass` placeholders)
- [ ] Every parameter is actually used

### 6. Break Into Phases

Phases are units of implementer work that fit one context window and one
reviewer pass. The number of phases falls out from the work — it is not
fixed, and there is no default shape (no Core/Extended/Integration trichotomy,
no one-phase-per-package rule).

A phase boundary is a place where:
- A subsequent phase cannot meaningfully start without this one (true dependency), OR
- Mixing the two would produce a phase too large for one implementer pass.
  Rough limits per phase: ~8 source files touched, ~5 existing test files
  migrated, or both kinds of work in the same phase when either is non-trivial.
  Count files that must be **read**, not just edited: a source change whose
  correctness depends on reading many *other* models — a recursive/structural
  projection over a deep config tree, or an exhaustive walk of a type catalog —
  is a context multiplier even when it edits few files. When the same deep
  surface must be re-read to author the tests, that doubling is the overflow.

Common boundaries to look for in any sprint:
- **Source change vs. existing-test migration.** Different context profiles —
  source reshape is bounded design work; test migration scales with the existing
  test count. Split them into separate phases when each migrated file is
  independently green after the change. **Do NOT split when the change is
  _atomic_** (see *Phase steps* below) — there the source change and the whole
  migration must land in one phase as a `steps` pipeline.
- **Per-package boundaries** when changes span packages — **only if the bundle
  declares `layout: monorepo`.** Under `layout: single-package` there is no
  package axis; split on work-shape alone.
- **New-test authorship vs. existing-test rewriting.**
- **Type/schema reshape vs. business-logic changes that use the new shape.**

Examples:
- One source file + three new tests → one phase.
- A grammar reshape that adds an _optional_ path and migrates 15
  independently-green test files → two phases (reshape, then migration).
- Under `layout: monorepo`, changes across three packages with independent test
  surfaces → likely three or more phases, split on package boundaries.

#### Phase steps (fresh-context decomposition)

A single implementer holds the whole phase in one context window: every source
file, every migrated test, the design doc, and all edits accumulate together.
When a phase mixes work-shapes (source reshape + test migration + hand-rewrites)
or carries a migration whose size scales with the existing test count, that one
window overflows. Overflow is driven by accumulated **context**, not tool count —
so the fix is structural: decompose the phase into **steps**, each a *fresh-
context* agent launch, recorded as data in the phase's `steps` block (Step 8).
The runner executes the steps in order, then runs the phase's
gate → review → fix → demo → commit tail **once** over the combined result. The
steps reset context accumulation; the gate-and-commit invariants stay frozen.

Emit a `steps` block when any holds:
- The phase mixes more than one work-shape (e.g. source reshape **and** existing-
  test migration that must land together — see *atomic*, below).
- The phase reshapes source **and** authors a large new test suite over the same
  deep config/type surface — e.g. an extraction projection plus tests that
  enumerate one assertion group per type/shape variant. New-test breadth drives
  context the way migration file-count does; split `source` from `author` even
  when no existing tests migrate. Use `[source, author]`.
- The phase is a single shape but too large for one window (e.g. migrating many
  existing test files, or authoring one enumerative new-test suite). Use a
  one-step pipeline (`[migrate]` or `[author]`).

An ordinary single-shape phase that fits one window carries **no** `steps` block —
the runner launches one implementer (the proven default). Do not decompose a
phase that does not need it.

**Step kinds:**

| kind | What it does | Runner launch |
|---|---|---|
| `source` | Source / schema / grammar reshape. Produces the new API. May leave the suite red — fine; the phase gate runs after all steps. Also creates the demo. | One implementer, fresh context. |
| `migrate` | Mechanically migrate existing test files to the new API (intent preserved). | **Fan-out by file** (default): one implementer per file, in parallel, fresh context each. Or `tactic: codemod` for a uniform slice (below). |
| `author` | New-test authorship, or intent-changing rewrites (a validator was removed, so assertions flip or disappear — per-file judgment against the spec). | One implementer per coherent group, fresh context. |

**Shrink at source first (prevention beats orchestration).** Before composing a
`migrate` step, check whether the migration can be designed away: centralize
construction through a shared builder, or append a benignly-defaulted _internal_
field so existing constructions still compile → migration drops to 0 and the
phase needs no `migrate` step at all. _Guard: internal runtime types only — a
default on an author **config** field is a Principle-#7 violation._

**Atomic vs. splittable.** A change is **atomic** when some intermediate state
leaves the suite red — a required field is added, or a validator is
removed/relaxed, so every un-migrated site fails until _all_ are migrated.
"Make it optional first, tighten later" is forbidden (the no-invented-values and breaking-changes principles).

- **Atomic** → the source change and the migration cannot be separate gated
  phases (the first would end red). Put them in **one phase** as a `steps`
  pipeline: `[source, migrate]` (add an `author` step if some assertions are
  intent-changing). The phase gate runs after the whole pipeline.
- **Splittable** → source reshape and migration are independently green; make
  them **separate phases** (the boundary rules above). Each is ordinary, or
  carries its own `steps` block if individually too large.

**Source + new-test authorship.** Authoring a large new test suite is always
*splittable* from the source it tests (the tests are writable once the source
lands). When source and the new suite both read the same deep config/type
surface, make it a `[source, author]` steps pipeline (or separate phases if the
suite is large enough to stand alone) so each reads that surface in its own
fresh context. A trivial migration does **not** license single-implementer when
the new-test authoring is large.

**Per-phase self-check.** Does writing this phase require reading the same deep
config/type surface twice — once for the source, once for the tests? If yes →
`[source, author]` steps, regardless of migration size.

**Migration tactic — fan-out is the default.** Test migration chunks naturally by
file: each per-file implementer stays small (~60–90k window), and there is no
cross-file consistency risk because every agent migrates against the _same_ new
source. Reach for `tactic: codemod` only when **one transform is uniform across
many files** (e.g. "add `enum_domains={}` as the 5th argument at every call
site") — there a single libcst/ast script amortizes. The codemod-able unit is
**per-transform, not per-phase**: if a migrate step mixes a uniform transform
with heterogeneous hand-edits, split it into two `migrate` steps (one `codemod`
for the uniform slice, one `fan-out` for the rest) rather than forcing the whole
migration through one script. A heterogeneous codemod earns nothing — it
collapses into single-file special-cases in one brittle script.

Each phase must:
- Be independently testable (its gates run green at phase end)
- Have a standalone demo script (if a phase has no natural demo, it is too
  small — merge it; see Step 7)
- List explicit test cases (not just test files)
- Build on previous phases (no forward references to later-phase contracts)

### 7. Define Demo Requirements

Demo scripts live in `docs/sprints/<sprint-name>/demos/`.

For each phase, specify:
- What the demo script demonstrates
- Sample config (embedded in demo)
- Expected output/behavior
- Success criteria

### 8. Create Artifacts

**Create `docs/sprints/<sprint-name>/spec.md`:**
```markdown
# Sprint: [Name]

## Purpose
[One sentence + author use case]

## Scope

**Capabilities touched:**
- capability1: sub-capability A, sub-capability B
- capability2: sub-capability C

**Not included:** [What's deferred]

## Breaking Changes

Document any changes to existing public interfaces, field types becoming optional,
constructor signatures changing, or validator behavior changing. For each:
- What changes
- Why existing configs/code still work (or don't)

Omit this section if the sprint is purely additive.

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Contracts
[Function signatures with docstrings — no implementation code]

## Phases

### Phase 1: [Name]
**Delivers:** [What]
**Demo:** [What it proves]
**Contracts:** [Which functions from this phase]
**Steps:** none (single implementer) — or the pipeline, e.g. `source → migrate (fan-out, 6 files) → author (1 file)` (see Step 6; mirrors the `state.yaml` `steps` block)

**Files:**
| Action | File |
|--------|------|
| Modify | `<src-tree>/<module>.py` |
| Create | `<test-tree>/<module>/test_<name>.py` |
| Create | `docs/sprints/<sprint-name>/demos/phase_<N>_<slug>.py` |

**Files tables list only source code, tests, and demo scripts.** Do NOT list architecture docs (`architecture/*.md`, `pending/*.md`, `capabilities.md`, `sprints.md`, `README.md`, `CAPABILITIES.md`). Architecture doc updates — including promoting `pending/*.md` to live and updating cross-references — ship in a separate commit after sprint archival (see Step 9), not through `/implement-sprint`. The implementer acts on every row in the Files table; listing `.md` docs there pulls doc writing into the code sprint and distorts phase scope.

**Tests:**
- Specific test case description (e.g., "Write single role twice: second overwrites first")
- Another specific test case
- Existing tests that must still pass

Test files go in the directory matching the code under test (e.g., `tests/journeys/` for journey code, `tests/config/rules/` for validation rules). Never create sprint-named test files or a `tests/sprints/` directory.

### Phase 2: [Name]
...

## What Doesn't Change

Explicit scope boundaries to prevent implementer drift. List functions, modules, or
behaviors that must NOT be modified even though they're adjacent to the work.

- [Function/module] stays as-is because [reason]
- [Existing behavior] is not affected because [reason]

## Module Changes Summary

Quick-reference table of all files touched across all phases. Mirrors the per-phase
Files tables — code, tests, and demo scripts only. No architecture docs.

| File | Change |
|------|--------|
| `path/to/file.py` | One-line summary of change |
```

**Update `docs/sprints/<sprint-name>/state.yaml`:**

`state.yaml` is the execution contract consumed by `/implement-sprint`. The orchestrator reads ONLY `spec.md` and `state.yaml` — so every command and path the orchestrator needs to run must live here. Do not assume defaults; emit the commands explicitly.

```yaml
sprint: sprint-name
parent_branch: <branch-where-sprint-was-created>   # captured per "Parent Branch" rule above
started: YYYY-MM-DD
current_phase: 1
capabilities:
  - <capability>: [<slice>, <slice>]
gates:
  # Pre-commit is NOT listed here — the implementer and reviewer agents each run
  # `pre-commit run --files <paths>` on the files they touched/reviewed.
  # The orchestrator only gates on tests.
  tests:
    # Scope to what this sprint touches, not the whole repo.
    # Each entry is a complete shell command that exits non-zero on any failure.
    # Prefer a `make test` target over a raw pytest line (it truncates output).
    - "cd <pkg> && make test"      # under layout: monorepo, one entry per package touched
    # under layout: single-package, one entry for the repo's test target
phases:
  1:
    status: pending
    name: "Short phase title — matches spec Phase 1 heading"
    demo: "docs/sprints/<sprint-name>/demos/phase_1_<slug>.py"
  2:
    status: pending
    name: "Short phase title — matches spec Phase 2 heading"
    demo: "docs/sprints/<sprint-name>/demos/phase_2_<slug>.py"
    # `steps` block ONLY when a phase mixes work-shapes or carries a migration
    # too large for one context window (see Step 6). Omit entirely for an
    # ordinary single-implementer phase. Steps run in declared order, each in a
    # FRESH context; the phase gate / review / fix / demo / commit tail runs
    # ONCE after all steps — so an atomic source+migrate phase may be red
    # between steps. That is expected.
    steps:
      - kind: source            # source/schema/grammar reshape; also creates the demo
        summary: "One line: the reshape this step makes"
      - kind: migrate           # mechanically migrate existing tests to the new API
        tactic: fan-out         # fan-out (default) | codemod (one uniform transform only)
        change: "One line: the API delta the files must adapt to"
        files:                  # disjoint existing test files (runner fans out one agent each)
          - "<test-tree>/<module>/test_<a>.py"
          - "<test-tree>/<module>/test_<b>.py"
      - kind: author            # new tests / intent-changing rewrites (per the spec)
        summary: "One line: what this step authors or rewrites"
        files:
          - "<test-tree>/<module>/test_<c>.py"
```

**Rules for emitting `gates.tests`:**

- Under `layout: monorepo`, include one entry per package touched by this sprint's phases (from the Module Changes Summary table), and skip packages that aren't modified — the post-sprint review runs full-suite coverage. Under `layout: single-package`, one entry for the repo's test target.
- Each entry must be a single self-contained shell command, in whatever form the repo's own test target takes (`cd <pkg> && make test` per package here).
- Do not include `--cov` flags or coverage thresholds. The per-package `make test` target already handles per-phase gating with `--no-cov`; coverage enforcement lives in post-sprint gates.

**Rules for emitting `phases.<N>.demo`:**

- Every phase has exactly one demo script. If a phase has no natural demo, the phase is too small — merge it.
- Path is relative to the repo root, matching the `Create` entry in the phase's Files table.
- The orchestrator executes `python <demo>` verbatim. The file must exist by the end of phase implementation.

**Rules for emitting `phases.<N>.steps`:**

- Emit the `steps` block **only** for a phase Step 6 flagged as mixed-shape or
  too-large for one window. Omit it entirely otherwise — its absence means
  "ordinary single-implementer phase."
- Steps run in declared order. Put a `source` step before any `migrate` / `author`
  step that depends on the reshaped API.
- `migrate.tactic` is `fan-out` unless **one uniform transform spans every file in
  the step** — then `codemod`. A migrate step that mixes a uniform transform with
  heterogeneous edits is split into two `migrate` steps (one `codemod`, one
  `fan-out`), not forced through one script.
- `migrate.files` and `author.files` list **disjoint existing files** (the runner
  fans out one agent per `migrate` file). `migrate` carries a one-line `change`
  (the API delta); `source` / `author` carry a one-line `summary`.
- The demo (`phases.<N>.demo`) is created during the pipeline by the first
  `source` step (or the first step if none is `source`).
- The `spec.md` **Steps:** line for the phase must match this block.

### 9. Commit the Sprint Scaffold

Commit `docs/sprints/<sprint-name>/` to the parent branch. The commit must exist before Step 10 forks the worktree (the worktree forks from `parent_branch` HEAD, which must already contain the sprint dir).

First capture the **baseline sha** — the parent HEAD the sprint's code builds on, read *before* this commit so it anchors real code, not the scaffold itself (a commit can never contain its own sha). Record it in `state.yaml` as `baseline_sha`, then commit:

```bash
BASELINE_SHA=$(git rev-parse <parent>)        # parent HEAD, pre-scaffold — the code baseline
# write into state.yaml:  baseline_sha: <BASELINE_SHA>
git add docs/sprints/<sprint-name>/
git commit -m "Sprint <sprint-name>: plan"
```

`baseline_sha` is the create-time anchor: the worktree forks from the scaffold commit (whose parent is `baseline_sha`), so reproducibility and seam-guard tooling know exactly what code the sprint was built on.

**Do not push.** The parent branch is local until the user explicitly pushes (typically after sprint ACCEPT).

### 10. Create and bootstrap the worktree

The scaffold is now committed at `<parent>` HEAD. Fork the worktree from it here, in `/create-sprint`, so `/implement-sprint` can launch *inside* it. This is what scopes the implement session's cclsp/LSP to the worktree instead of the main checkout — a soft `cd` cannot re-root an already-running language server, so the worktree must exist before that session starts.

**Collision checks** — halt on any hit; the user must clean up a prior attempt themselves (`git worktree remove --force ../worktrees/<sprint-name>`, `git branch -D sprint/<sprint-name>`):

```bash
git show-ref --quiet "refs/heads/sprint/<sprint-name>"        # branch must NOT exist
test -e "../worktrees/<sprint-name>"                          # worktree path must NOT exist
git worktree list | grep -q "../worktrees/<sprint-name>"      # not registered as a worktree
```

**Validate the plan against `<parent>`** — do this *before* creating the worktree, so a mis-pathed plan fails in seconds instead of after a 30–60s sync. These are pure-git lookups against `<parent>` HEAD — no checkout, no venv. For every file in every phase's Files table:

```bash
git cat-file -e "<parent>:<path>"   # exit 0 = path present at parent HEAD
```

- **Create** rows must be **absent** (`git cat-file -e` exits non-zero). A path that already exists means the verb is wrong — it's a Modify.
- **Modify** and **migrate** `files:` rows must be **present** (exit 0). An absent path is a stale or mistyped plan entry.
- Every `phases.<N>.demo` path must appear as a **Create** row in that phase's Files table.

Any mismatch halts — fix the plan (Step 6) before continuing. Nothing has been created yet, so there is nothing to clean up.

**Create the worktree:**

```bash
mkdir -p ../worktrees
git worktree add "../worktrees/<sprint-name>" -b "sprint/<sprint-name>" "<parent>"
```

**Bootstrap the environment.** Detect single uv workspace vs. per-package projects, then sync:

```bash
if test -e "../worktrees/<sprint-name>/pyproject.toml"; then
    (cd "../worktrees/<sprint-name>" && uv sync --all-extras)
else
    for pkg in "../worktrees/<sprint-name>"/packages/*/; do
        test -e "$pkg/pyproject.toml" && (cd "$pkg" && uv sync --all-extras)
    done
fi
```

`--all-extras` is mandatory: dev-only path dependencies (a sibling package pulled in for tests) commonly live in `[project.optional-dependencies]`, and a plain `uv sync` omits them — the first gate run then fails on a `ModuleNotFoundError` that is an environment gap, not a sprint-code bug. Do not pass `--no-dev`: the repo-wide type-check pre-commit hook (the bundle's `typecheck-hook`) runs `uv run mypy`, and mypy + its stubs live in the default `dev` group. This installs editable packages into each `.venv`, isolating the sprint's test environment from the main checkout. Expect 30–60s on first run.

**Gate the parent baseline:**

```bash
(cd "../worktrees/<sprint-name>" && pre-commit run --all-files)
```

The worktree is a clean checkout of `<parent>` HEAD, so this gates the exact baseline the sprint builds on. If it fails, **halt** — `<parent>` does not pass pre-commit cleanly; phase commits could not attribute a hook failure to sprint changes, and auto-fixing hooks leave the worktree dirty. Remove the worktree and branch (commands above) and tell the user to fix `<parent>` before re-running.

**Gate the baseline test suites:** run every command in `state.yaml:gates.tests`, in order, from the worktree:

```bash
cd "../worktrees/<sprint-name>"
# for each command in gates.tests: run it; halt on the first non-zero exit
```

This is the same bar the phases are held to, run once on the clean baseline. A red baseline means later mid-sprint failures could be pre-existing parent breakage (drift, flake, env-specific) rather than sprint code — gating here makes every phase failure unambiguously the sprint's. If any gate fails, **halt** with the failing command and tell the user to fix `<parent>` before re-running (remove the worktree and branch first). Cost is a few minutes once per sprint; if a known-green parent makes it redundant, the user may skip with `--skip-baseline-tests`.

### 11. Hand off to the worktree session

cclsp roots at the directory Claude launches from. To get a worktree-scoped LSP — and to make a stray write or commit to the parent branch structurally impossible — `/implement-sprint` must run from a session started *inside* the worktree.

Print this for the user to run in a new terminal:

```bash
cd ../worktrees/<sprint-name> && claude
```

then, inside that session:

```
/implement-sprint <sprint-name>
```

### 12. Update Status

After sprint completes (post-ACCEPT):
- Update `docs/CAPABILITIES.md` status markers for touched capabilities
- Update `docs/architecture/README.md` router if new package architecture docs were added
- `/implement-sprint` ACCEPT removes `docs/sprints/<sprint-name>/` as the final commit before merging the sprint branch back into parent

## Quality Checks Before Done

- [ ] Scope approved by user
- [ ] Purpose is clear and author-focused
- [ ] Capabilities touched are explicit
- [ ] Breaking changes documented (or section omitted if purely additive)
- [ ] All contracts have full signatures + docstrings
- [ ] NO default parameters in any contract (the no-invented-values principle)
- [ ] NO scaffolding for future work (the no-future-scaffolding principle)
- [ ] NO implementation code in contracts (signatures and docstrings only)
- [ ] Anti-scaffolding checklist passed
- [ ] Phases are independently testable
- [ ] Each phase has explicit test case bullets (not just file names)
- [ ] Demo requirements specified per phase
- [ ] "What Doesn't Change" section present
- [ ] Module Changes Summary present
- [ ] spec.md created
- [ ] state.yaml updated
- [ ] state.yaml has `parent_branch` set (auto-created `<sprint-name>-work` if user was on main/master)
- [ ] Sprint name does not collide with an existing sprint dir, branch, or worktree
- [ ] state.yaml has `gates.tests` (list of commands, one per touched package)
- [ ] state.yaml does NOT have `gates.precommit` (implementer and reviewer handle pre-commit themselves)
- [ ] state.yaml has `phases.<N>.name` and `phases.<N>.demo` for every phase
- [ ] Every `demo` path in state.yaml matches a `Create` row in the phase's Files table
- [ ] `steps` block present only on mixed-shape or oversized phases (ordinary phases omit it); every `migrate` step defaults to `tactic: fan-out`, with `codemod` reserved for a single uniform transform; `migrate`/`author` `files` are disjoint
- [ ] No Files table contains an architecture doc path (`architecture/*.md`, `pending/*.md`, `capabilities.md`, `sprints.md`, `README.md`, `CAPABILITIES.md`). Doc migrations ship separately (Step 12)
- [ ] Sprint dir committed to parent branch (Step 9)
- [ ] `state.yaml` has `baseline_sha` (parent HEAD pre-scaffold, Step 9)
- [ ] Plan validated against `<parent>`: Create paths absent, Modify/migrate paths present, every demo path is a Create row (Step 10)
- [ ] Worktree created at `../worktrees/<sprint-name>` on branch `sprint/<sprint-name>` (Step 10)
- [ ] Worktree venv synced (`uv sync --all-extras`) and parent baseline pre-commit passes (Step 10)
- [ ] Baseline `gates.tests` pass on the clean worktree (Step 10, unless `--skip-baseline-tests`)
- [ ] Launch handoff printed (`cd ../worktrees/<sprint-name> && claude`) (Step 11)

## Code Navigation

When exploring existing code during planning, navigation is cclsp-first — follow `.claude/worker-protocol.md` § Code Navigation.

Reserve Grep for pattern searches (anti-patterns, TODOs, regex matching).

## When to Use Architect Agent

Invoke the **architect** agent when you need to:
- Design complex interfaces
- Make architectural decisions
- Update architecture docs
- Resolve design ambiguities
