---
name: implement-sprint
description: Automated sprint implementation in a worktree with context discipline and quality gates.
argument-hint: [sprint-name]
disable-model-invocation: true
---

# Implement Sprint

Automated sprint implementation in an isolated worktree with binding quality gates. Runs all phases without stopping, presents results for ACCEPT or FIX.

## Argument

`/implement-sprint <sprint-name>` — required when more than one sprint dir exists with at least one phase still `pending`. If exactly one such sprint exists, the name may be omitted and is auto-detected from `docs/sprints/*/state.yaml`.

## Conventions

Throughout this skill:
- `<sprint>` — the sprint name
- `<parent>` — value of `state.yaml:parent_branch` (the branch the worktree forks from and the sprint eventually merges back into)
- `<worktree>` — `../worktrees/<sprint>` (sibling of the main checkout); **this session runs inside it** (cwd == the worktree's repo top)
- `<sprint-branch>` — `sprint/<sprint>` (created by `/create-sprint` when it forked the worktree)

## Orchestrator Role

You are a **router**, not a judge. You launch agents, run automated gates, and relay results. You do NOT interpret technical findings or make quality decisions about code you haven't read.

**Binding rules:**

1. If a reviewer returns `VERDICT: REVISIONS NEEDED`, you MUST launch a fixer agent. You may NOT dismiss, reinterpret, or skip any finding.
2. If you disagree with a finding, include your disagreement alongside the finding in the final presentation. The user decides — you do not.
3. You never evaluate whether code is "intentional," "acceptable," or "a known pattern." Route findings; don't filter them.
4. **Gates run once.** Each test command in `state.yaml:gates.tests` runs exactly once per phase. Any non-zero exit halts automation. You do NOT retry with variant flags, read source files to diagnose, or launch subagents to debug gate failures. Report and halt.
5. **You are inside the worktree and never leave it.** This session was launched from `<worktree>`, so cwd is the worktree's repo top; every read, write, gate, and commit stays here. The main checkout is the user's space — never reference an absolute path under it. If a tool (e.g. cclsp) returns a main-checkout path, it is wrong — re-resolve it against cwd before reading or editing.
6. **Within the worktree, only touch sprint-scoped files.** Commit only the files your implementer reported (`git add <paths>`), never `git add -A`. The worktree was forked clean from `<parent>`, so this is paranoia not necessity — but it stays as a binding rule.

## Prerequisites

- Sprint scaffold committed at `docs/sprints/<sprint>/` on `<parent>` (created by `/create-sprint` or `/create-sprint-from-pending`)
- `state.yaml:parent_branch` is set
- Contracts in `spec.md` are fully defined
- The worktree exists and is bootstrapped (`/create-sprint` Step 10)
- **This session was launched from inside `<worktree>`** (`cd ../worktrees/<sprint> && claude`), so its cclsp/LSP is worktree-scoped

## Pre-Flight Checks

Run these in order. Do NOT skip or reorder.

### 1. Assert this session is inside the sprint worktree

The worktree was created and bootstrapped by `/create-sprint` (Step 10), and this session must have been launched from inside it (`cd ../worktrees/<sprint> && claude`). That launch is what scopes cclsp/LSP, cwd, and git to the worktree — it is the entire safety mechanism. Verify it before doing anything else:

```bash
git rev-parse --show-toplevel     # must end with /worktrees/<sprint>
git branch --show-current         # must equal sprint/<sprint>
git rev-parse --git-common-dir    # differs from --git-dir → confirms a linked worktree
```

If the toplevel is the **main checkout** (not under `worktrees/`), **halt** — do not create anything, do not proceed:

> `/implement-sprint` must run from inside the worktree, or cclsp leaks main-checkout paths and a stray write/commit can land on the parent branch. Run:
> ```
> cd ../worktrees/<sprint> && claude
> ```
> then re-run `/implement-sprint <sprint>` in that session.

If the worktree does not exist at all, `/create-sprint` did not complete — halt and tell the user to re-run it.

### 2. Resolve sprint name

If the user passed `<sprint>` as an argument, use it. Otherwise derive it from the current branch (`sprint/<sprint>`), falling back to the unique `docs/sprints/*/state.yaml` with at least one `pending` phase. If ambiguous, halt and ask the user to specify.

### 3. Read state.yaml and spec.md

From the worktree (cwd), read `docs/sprints/<sprint>/state.yaml`:

- `sprint` — must equal `<sprint>`
- `parent_branch` — must be set; this is `<parent>`, and `<sprint-branch>` must descend from it (sanity-confirms the worktree's lineage)
- `gates.tests` — list of shell commands
- `phases.<N>.name` and `phases.<N>.demo` for every phase
- At least one phase with `status: pending`

If any field is missing, halt — the sprint plan is incomplete and should be re-emitted by `/create-sprint`.

Then read `docs/sprints/<sprint>/spec.md` once, upfront, only to confirm the sprint name in the H1 matches `<sprint>`.

User-facing status line:

> Inside worktree `<worktree>` on branch `<sprint-branch>` forked from `<parent>`. All phase work runs here.

### 4. Subagent execution model

Every subagent in this skill runs as a **foreground `Agent` call**: the call blocks inline until the subagent finishes and returns its **final message directly** as the tool result. One turn, one cache-read, no transcript.

There is nothing to activate — foreground is the default. Do NOT launch a phase agent in the background and retrieve it via `TaskOutput` or by reading its `.output` file: for a local agent that file is the full conversation transcript and will overflow your context. The final message is all you ingest.

## Context posture

**Task-scoped — the sprint spec and `state.yaml`, nothing else.** Do NOT run
`/understand`; do NOT load architecture docs. You are the orchestrator, and
every token you spend on background is a token unavailable for driving phases
to completion. The implementer agent loads whatever the code needs, in its own
context.

## Context Budget Rules

These rules prevent context exhaustion. Follow them exactly.

### Rule 1: Orchestrator Reads Minimally

You (the orchestrator) read ONLY these files:

| File | Purpose |
|------|---------|
| `docs/sprints/<sprint>/spec.md` | Sprint spec — read ONCE, upfront |
| `docs/sprints/<sprint>/state.yaml` | Phase status, gates, demo paths, parent branch |

Everything you need to execute lives in `state.yaml`:

- `parent_branch` — `<parent>` for worktree fork and final merge
- `gates.tests` — the list of test commands
- `phases.<N>.demo` — the demo path for phase N
- `phases.<N>.name` — the phase title for subagent prompts

Pre-commit is not an orchestrator gate — the implementer runs and fixes it, the reviewer re-runs it and reports.

**Do NOT read source files, architecture docs, config models, or any `.py` file.** Do NOT re-read `spec.md` to find demo paths or phase titles — they are in `state.yaml`. The implementer agent reads whatever it needs.

### Rule 2: Subagent Prompts Are Brief

Pass to agents:
- Phase number and title (from `state.yaml:phases.<N>.name`)
- Sprint spec path: `docs/sprints/<sprint>/spec.md`
- Worktree path so the agent operates in the right tree
- One sentence summarizing the phase goal
- The quality/output rules block (standardized, see templates below)

**Do NOT paste code, file contents, contracts, or implementation details into prompts.** Exception: the fixer prompt includes the reviewer's response verbatim.

### Rule 3: Block Inline on the Agent Call — Never Wake-and-Poll

Launch each subagent as a **foreground `Agent` call** (no `run_in_background`). The call blocks inline until the subagent returns its final message directly — one turn, one cache-read, done. There is no timeout to manage; a foreground call waits as long as the subagent needs.

**Forbidden patterns** (all force the orchestrator to re-read its full context to make zero forward progress):

- Launching a phase agent with `run_in_background: true`, then retrieving it via `TaskOutput` or by reading its `.output` file — that ingests the full transcript and overflows context
- Using `ScheduleWakeup` to wait for a subagent
- Polling `/tmp/.../tasks/*.output` with `Bash` + `tail`
- Waiting for an automatic completion notification to arrive on its own

Block inline on the foreground `Agent` call. Period.

### Rule 4: No Accumulation Between Phases

After committing a phase, the worktree's git history is your record. Do NOT retain mental summaries of what each phase did. Commit messages and `state.yaml` track progress.

Exception: retain the review verdict (APPROVED or list of unresolved findings) for the final presentation.

## Automation Model

```
/implement-sprint
       |
+------------------------------------------+
|  PRE-FLIGHT                              |
|  Resolve name, read state, verify parent,|
|  create worktree, uv sync, switch cwd    |
+------------------------------------------+
       |
+------------------------------------------+
|  AUTOMATED (no human intervention)       |
|                                          |
|  For each phase (inside worktree):       |
|    1. Implement                          |
|       (steps pipeline if declared:       |
|        source → migrate(fan-out) → author,|
|        each a fresh-context agent)        |
|    2. Tests                              |
|    3. Review                             |
|       ├─ APPROVED → step 5              |
|       └─ REVISIONS NEEDED               |
|          4. Fix cycle (max 3)            |
|          └─ 3 failures → STOP           |
|    5. Demo                               |
|    6. Analyze data (if applicable)       |
|    7. Commit + git notes                 |
|                                          |
|  After all phases (inside worktree):     |
|    8. /review-sprint                     |
|       ├─ no blockers → step 9           |
|       └─ blockers → fix loop (max 3)    |
|          └─ 3 failures → STOP           |
|       (observations never enter loop)   |
|    9. Run all demos twice                |
|   10. Completion checks                  |
+------------------------------------------+
       |
+------------------------------------------+
|  PRESENT TO USER                         |
+------------------------------------------+
       |
   User Decision
       |
+-------------+-------------------+
|   ACCEPT    |       FIX         |
|             |                   |
| Rebase &    | Address issues    |
| merge to    | inside worktree,  |
| <parent>    | re-commit         |
+-------------+-------------------+
```

**Key principle:** The worktree contains the entire sprint. ACCEPT folds it into `<parent>`; FIX leaves it open for more iteration. There is no RESET path — abandoning a sprint is a manual `git worktree remove --force <worktree> && git branch -D <sprint-branch>`.

## Process Details

### Phase Implementation (Automated, in worktree)

For each phase in the sprint:

#### Step 1: Implement

**First, check `state.yaml:phases.<N>.steps`.**

- **No `steps` block** → ordinary phase. Launch the single **implementer** agent
  with the standard template below (the proven default — skip to the template).

- **`steps` block present** → the phase is decomposed into fresh-context steps to
  avoid overflow. Run them **in declared order**, each as its own `Agent`
  launch — a fresh context per step is exactly what prevents accumulation. Do
  NOT run the gate, review, or commit between steps: the phase tail (Step 2
  onward) runs **once** after the whole pipeline, so the suite may be red between
  steps — expected. Route each step by `kind`:

  - **`source`** — one implementer, fresh context. Use the standard template
    below, adding one `STEP GOAL:` line after the spec-reading line, scoped to the
    step's `summary` (e.g. "STEP GOAL: make the source/schema reshape for Phase
    {N}; do NOT migrate existing tests"). The `source` step (or the first step, if
    none is `source`) also creates the demo.

  - **`migrate`** — migrate the step's `files` to the new API:
    - `tactic: fan-out` (default): launch **one implementer per file in
      `files`**, all as `Agent` calls **in a single turn** (parallel). Give each
      the MIGRATE block below, scoped to its one file. Disjoint files, same
      worktree, no git ops → no conflicts, no worktree isolation needed.
    - `tactic: codemod`: launch **one** implementer with the CODEMOD block below;
      it writes a libcst/ast script and runs it across all `files` in one pass.

  - **`author`** — one implementer per `author` step, fresh context. Standard
    template, adding one `STEP GOAL:` line scoped to the step's `summary` (new
    tests / intent-changing rewrites per the spec).

  After the last step, proceed to Step 2 (Tests) for the whole phase.

  **MIGRATE block** (one per file, fan-out — a focused implementer prompt):

  ```
  Migrate one test file to the reshaped API — Phase {N} of the {sprint} sprint.

  Working directory: <worktree>. All paths absolute. Invoke Python via `uv run python`.
  Sprint spec: docs/sprints/<sprint>/spec.md (read Phase {N} for context).

  CHANGE: {step.change}
  FILE (migrate ONLY this file): {one path from step.files}

  RULES:
  - Read the new source modules this test imports to learn the new signatures
    (cclsp-first: find_definition / get_hover). Do NOT change source.
  - Hand-edit this one file to pass against the new API. Mechanical migration only —
    preserve each test's intent; do not delete assertions or add new test cases.
  - No codemod, no scripts, no git operations. Touch ONLY this file.
  - Do NOT run the full gate (the suite is red until the whole phase lands). You may
    run `uv run pytest <this file>` to check this file in isolation.

  OUTPUT (mandatory, <1000 chars):
  - The file you migrated
  - Test result for THIS file (pass/fail count)
  - Any signature you could not resolve (so the orchestrator can flag it)
  ```

  **CODEMOD block** (one implementer, uniform-transform slice only):

  ```
  Atomic codemod migration — Phase {N} of the {sprint} sprint.

  Working directory: <worktree>. All paths absolute.
  Sprint spec: docs/sprints/<sprint>/spec.md (read Phase {N} for context).

  This step is ONE uniform transform across these files:
  {step.files}
  TRANSFORM: {step.change}

  1. Write a libcst (or ast) codemod script that applies the transform to every file.
  2. Run it across all of them in one pass. Hold the SCRIPT in context, not N files.
  3. The suite is red until the whole phase lands — do NOT gate here.

  OUTPUT (mandatory, <1000 chars): the script path, files transformed, per-file result.
  ```

Launch the **implementer** agent. Your prompt MUST follow this template exactly:

```
Implement Phase {N}: {Title} for the {sprint} sprint.

Working directory: <worktree>
All paths absolute. The worktree's .venv is the sprint's environment — invoke
Python via `uv run python` from the worktree root.

Sprint spec: docs/sprints/<sprint>/spec.md
Read the spec, focus on Phase {N}. Read source files as needed.

QUALITY RULES (mandatory):
- Decompose into module-level functions, not inner closures — helpers must be independently testable
- If two modules share logic, extract it into a shared module (DRY)
- Check every success criterion in the spec — missing deliverables (examples, configs) count as failures
- Use TYPE_CHECKING for type-only imports; keep runtime imports minimal
- Do not add a `# type: ignore` mypy does not require — `warn_unused_ignores` is on, so an unneeded ignore fails the hook
- Remove stale comments (sprint changelog comments, "# Future:", scaffolding markers)
- No code duplication — if you copy-paste and modify, extract a shared function instead
- Place tests in the module directory matching the code under test (e.g., tests/journeys/ for journey code). Never create sprint-named test files or a tests/sprints/ directory.

CODE NAVIGATION (mandatory — cclsp-first for any named symbol; never Grep/Read whole files for one. Backend: basedpyright; all tools work):
- find_definition / find_references: where defined / all usages
- get_incoming_calls / get_outgoing_calls: callers / callees — trace a call chain across module and package boundaries
- find_workspace_symbols: locate a symbol by name when you don't know its file
- get_hover: type info/docs without reading the whole file
- Reserve Grep for non-symbol text (concepts, TODOs, regex, YAML). A timeout just after server start = indexing, retry once.

DELIVERABLES (mandatory):
- Implementation code for this phase (all files in the phase's Files table)
- Tests in the directory matching the code under test
- Demo script at the exact path from `state.yaml:phases.<N>.demo` — you MUST create this file before returning. Do not defer demo creation.
- Pre-commit passes on the files you touched: run `pre-commit run --files <every file you edited or created>` and iterate until it exits 0 (max 3 runs). The repo-wide type-check hook (the bundle's `typecheck-hook`) checks every source tree regardless of which files you pass, so a type error may surface OUTSIDE your diff. Under `layout: monorepo` the usual cause is a signature change here breaking a caller in another package. Either way it is a real failure to fix (or revert the breaking change), not environment noise. For fast type-only iteration, run mypy directly over the source tree you touched before the final pre-commit gate. The orchestrator does not run pre-commit — your phase is not done until pre-commit is clean.

OUTPUT RULES (mandatory):
- Final response MUST be under 2000 characters
- List files modified/created (paths only, no contents)
- `DEMO: <path>` — the demo file you created (must match `state.yaml:phases.<N>.demo`)
- `PRE-COMMIT: PASS` or `PRE-COMMIT: FAIL — <reason>` (per self-gate)
- Test result: pass count and fail count
- One-line summary per file change
- DECISIONS: List 1-3 key implementation decisions. One line each.
- Do NOT include code snippets, stack traces, or implementation details
- Do NOT re-read files you have already read

ITERATION LIMITS:
- Max 3 attempts to fix any single failing test
- Max 3 attempts to fix a demo script
- Never read the same file more than twice
```

**Do NOT add anything else to the prompt.** (A `steps`-pipeline phase uses the per-step prompts above — the MIGRATE / CODEMOD blocks for a `migrate` step, or this template with a scoped goal sentence for a `source` / `author` step.) No file contents, no contracts, no code patterns.

Launch as a **foreground `Agent` call** (no `run_in_background`). Emit exactly this user-facing status line, then make the Agent call in the same turn:

> Phase {N} implementer running. Blocking inline until it returns (may take several minutes).

The call blocks until the implementer returns its final message directly. This status line is MANDATORY before every long-running phase agent launch.

#### Step 2: Tests

Run each command in `state.yaml:gates.tests` in order, **inside the worktree**. Each runs exactly ONCE:

```bash
cd <worktree>
for cmd in {state.yaml:gates.tests}; do
    $cmd    # non-zero exit => halt automation
done
```

The per-package `make test` targets truncate output: one summary line on pass, ~60 lines on fail.

**If any test command fails:** STOP automation immediately. Report:
- The failing command
- The captured output
- Which phase triggered it

Do NOT:
- Try variant pytest invocations (`--no-cov`, `--cov`, different paths)
- Read source files to diagnose
- Launch another subagent
- Attempt to edit code yourself

This is a gate, not an investigation. One attempt, one verdict.

#### Step 3: Review

Launch the **reviewer** agent. Your prompt MUST follow this template:

```
Review Phase {N}: {Title} of the {sprint} sprint.

Working directory: <worktree>
All paths absolute.

Sprint spec: docs/sprints/<sprint>/spec.md
Focus on Phase {N} only.

Check the changes for this phase:
  git diff HEAD

PRE-COMMIT CHECK (mandatory):
Run `pre-commit run --files <every file in the diff>` once. Any non-zero exit (real violation OR auto-fix modification) is a REVISIONS NEEDED finding. Do not re-run, do not fix — report the failing hook output verbatim. The repo-wide type-check hook (the bundle's `typecheck-hook`) checks every source tree: a reported type error may live in a file outside this diff — under `layout: monorepo`, typically a cross-package break from this phase's changes. That is still a finding.

DO NOT use `git stash` or any destructive git command. Run pre-commit against the working tree as-is.

QUALITY CHECKS (in addition to standard review):
- Are helpers module-level functions (not closures/nested defs)?
- Any code duplication over 10 lines?
- Any Phase {N} success criteria from the spec not delivered?
- Any runtime imports that should be TYPE_CHECKING only?
- Any stale sprint comments left in modified files?
- Does the implementation include work that the spec assigns to a LATER
  phase (backward scope creep)? Check the spec's later-phase Files tables
  and Module Changes Summary before flagging.

DO NOT flag as findings at phase review:
- New symbols/helpers/validators that are exported but not yet called from
  production code, IF a later phase of this sprint will consume them.
  Cross-check the spec's later-phase Contracts and Files tables. Principle
  #8 (no future scaffolding) is enforced at sprint-level review, where the
  end state is visible — not at phase boundaries, where mid-sprint
  scaffolding for in-sprint consumers is the expected state.
- Migrations of files the spec assigns to a later phase.

The phase reviewer enforces Phase {N} scope and quality. The sprint-level
reviewer (`/review-sprint`) enforces end-state no-future-scaffolding and full-spec
delivery.

CODE NAVIGATION (cclsp-first): use find_definition / find_references / get_incoming_calls / get_outgoing_calls for any named symbol. Grep only for non-symbol text.

OUTPUT FORMAT (mandatory — follow exactly):

VERDICT: APPROVED
PRE-COMMIT: PASS

or

VERDICT: REVISIONS NEEDED
PRE-COMMIT: PASS | FAIL
FINDINGS:
- [file:line] description of required change
- [pre-commit] hook output verbatim (if PRE-COMMIT: FAIL)

Final response MUST be under 1500 characters.
Use ONLY the verdict format above. No prose before the verdict line.
```

Launch as a foreground `Agent` call (reviewer is fast).

**Routing (mechanical — no interpretation):**

| Verdict | Action |
|---------|--------|
| `VERDICT: APPROVED` | Proceed to Step 5 (Demo) |
| `VERDICT: REVISIONS NEEDED` | Proceed to Step 4 (Fix Cycle) |

#### Step 4: Fix Cycle

When the reviewer returns `VERDICT: REVISIONS NEEDED`, launch the **implementer** agent:

```
Fix review findings for Phase {N}: {Title} of the {sprint} sprint.

Working directory: <worktree>
All paths absolute.

Sprint spec: docs/sprints/<sprint>/spec.md
Read the spec for Phase {N} context, then fix the findings below.

REVIEWER FINDINGS (must be addressed):
{paste the reviewer's full response verbatim — do not summarize or filter}

RULES:
- Address every finding listed above
- If a finding is genuinely incorrect, state DISPUTED with a one-line reason — do NOT silently skip it
- Run tests after fixes to verify nothing breaks
- Do not make changes beyond what the findings require
- Use cclsp to navigate code (find_definition / find_references / get_incoming_calls), not Grep for definitions or call sites

OUTPUT RULES (mandatory):
- Final response MUST be under 1500 characters
- For each finding: FIXED or DISPUTED (with one-line reason)
- List files modified (paths only)
- Test result: pass count and fail count
- `PRE-COMMIT: PASS` — re-run `pre-commit run --files <touched files>` after fixes and iterate until exit 0; if not clean in 3 runs, report `PRE-COMMIT: FAIL — <reason>`
```

Launch as a **foreground `Agent` call** (no `run_in_background`). Emit exactly this user-facing status line, then make the Agent call in the same turn:

> Phase {N} fixer running. Blocking inline until it returns (may take several minutes).

The call blocks until the fixer returns its final message directly.

After the fixer completes:

1. Run tests (Step 2)
2. Re-launch reviewer (same prompt as Step 3)

**Max 3 fix cycles per phase.** After 3 cycles still returning `REVISIONS NEEDED`:
- STOP automation
- Do NOT commit the phase
- Collect the unresolved findings for the final presentation
- Report to user immediately

#### Step 5: Demo

Read `state.yaml:phases.<N>.demo`. Run it from the worktree:

```bash
cd <worktree>
uv run python {state.yaml:phases.<N>.demo}
```

Demo must run without errors and exit 0. If it fails, STOP and report.

#### Step 6: Analyze Data (If Applicable)

If the demo produces a data artifact, launch the agent named by the bundle's
`output-judge-agent` (`data-analyst` here, `ops-gate` in a repo that judges
exports). Read the name with `load.py . --field output-judge-agent` if it is not
already in context:

```
Analyze output from Phase {N} demo of the {sprint} sprint.

Working directory: <worktree>
Demo script: {state.yaml:phases.<N>.demo}
Run the standard validation workflow from your instructions.

OUTPUT RULES (mandatory):
- Final response MUST be under 1500 chars
- Use VALIDATION: PASS or VALIDATION: ISSUES FOUND format
```

#### Step 7: Commit Phase

Update `docs/sprints/<sprint>/state.yaml` to mark the phase complete and bump `current_phase`. Then commit **only the files the implementer reported** plus the state.yaml. All commands run inside `<worktree>`. Never `git add -A`.

```bash
cd <worktree>
git add docs/sprints/<sprint>/state.yaml \
    <file-1-from-implementer> \
    <file-2-from-implementer> \
    ...

git commit -m "$(cat <<'EOF'
Sprint <sprint> - Phase N: <Title>

- <What this phase implemented>
- Tests: PASS
- Pre-commit: PASS
- Review: APPROVED [or: APPROVED after N fix cycles]

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

List every path the implementer reported — implementation files, tests,
and the demo — explicitly. `git diff --name-only` is NOT a shortcut for
this: it lists only tracked-modified files and silently omits newly
created ones, so a new test file slips past its phase commit. Add new
files by their reported path.

After committing, verify nothing sprint-scoped was left behind:

```bash
cd <worktree>
git status --porcelain | grep '^??' && echo "UNTRACKED FILES REMAIN — halt" || echo "clean"
```

Any untracked file under a path the implementer reported means a
deliverable was missed — add it and amend the commit before proceeding.

#### Step 7b: Attach Sprint Notes

After the commit succeeds, attach a structured note to the commit:

```bash
cd <worktree>
git notes --ref refs/notes/agent/sprint add -m "$(cat <<'EOF'
{
  "sprint": "<sprint>",
  "phase": N,
  "decisions": [
    "<from implementer DECISIONS output — 1-3 lines>"
  ],
  "review_cycles": N,
  "findings_fixed": ["<from fixer output, if any>"],
  "findings_disputed": ["<from fixer output, if any>"],
  "files_created": ["<from implementer output>"],
  "files_modified": ["<from implementer output>"]
}
EOF
)" HEAD
```

Notes are written to the shared `refs/notes/agent/sprint` ref, visible from the main checkout after sprint ACCEPT.

**If the git notes command fails**, log a warning and continue. Notes are supplementary — never block the sprint on them.

### Post-Implementation (Automated, in worktree)

After all phases complete:

#### Step 8: Review Sprint — with fix loop

Run `/review-sprint <sprint>` for a comprehensive fresh-eyes audit. The
review skill operates in the worktree and reads `state.yaml:parent_branch`
for the diff base. It records findings in `docs/sprints/<sprint>/review.md`
and does NOT file `finding` notes.

The sprint-level review classifies each finding as **blocker** or
**observation** (recorded in `docs/sprints/<sprint>/review.md`). The two route
differently:

- **Blockers** are binding, exactly like a per-phase reviewer verdict — not
  advisory. Every blocker gets fixed, or the sprint stops.
- **Observations** (cosmetic / non-load-bearing — e.g. a DRY nit on otherwise
  green code) are **never auto-fixed**. They do not gate ACCEPT and do not
  consume fix cycles. They are surfaced for the user's per-item decision at the
  checkpoint (see Present to User).

Routing on the review result:

| Review result | Action |
|---|---|
| No blockers (clean, or observations only) | Proceed to Step 9; carry observations to the presentation |
| One or more **blockers** | Enter the blocker fix loop below |

**Blocker fix loop (max 3 cycles):**

1. Launch the **implementer** (fixer) agent with the Step 4 fixer prompt
   template, pasting **only the blocker findings** verbatim from `review.md`.
   Do NOT feed observations into the loop.
2. After the fixer returns, run the test gates (Step 2).
3. Commit the fixes (Step 7 commit rules — explicit paths, untracked-file
   check), message `Sprint <sprint> - review cleanup`.
4. Re-run `/review-sprint <sprint>`.
5. If the re-review has no blockers, proceed to Step 9. Otherwise repeat.

**After 3 cycles with blockers still open:** STOP automation. Collect the
unresolved blockers and any the fixer marked `DISPUTED` (the "cannot be fixed
in this sprint" case). Report all of them to the user and halt — do NOT proceed
to ACCEPT.

**Observations never halt the sprint.** A sprint that is green with only
observations proceeds to Step 9 and is presented as mergeable — an
`APPROVED-WITH-NOTES` state. The observations are listed for the user, who
decides at ACCEPT/FIX whether to fix or accept each.

**`finding` notes are never created automatically.** When the sprint stops with
unresolved or disputed blockers — or the user wants an accepted observation
tracked — present them and tell the user: *instruct me to file a `finding` note
if you want one tracked.* Only an explicit human instruction creates a note.

#### Step 9: Run All Demos Twice

```bash
cd <worktree>
for demo in {state.yaml:phases.*.demo}; do
    uv run python "$demo"
done

for demo in {state.yaml:phases.*.demo}; do
    uv run python "$demo"
done
```

Both runs must produce consistent output.

#### Step 10: Completion Checks

```bash
cd <worktree>
git status --porcelain | grep "^??"
git grep -n "# Future:" -- ':(glob)**/src/**/*.py'
git grep -n "    pass$" -- ':(glob)**/src/**/*.py'
```

Pre-commit is not run here — every phase's implementer and reviewer already validated the files they touched.

### Present to User

Show:
1. **Worktree location:** `<worktree>` on `<sprint-branch>` forked from `<parent>`
2. **Summary:** What was built, files changed
3. **Tests:** Pass/fail count
4. **Review findings:** For each phase, list all reviewer findings and their resolution (FIXED, DISPUTED, or UNRESOLVED). Include the reviewer's original text — do not paraphrase.
5. **Demos:** Sample output proving it works
6. **Unresolved blockers:** Any blockers that survived 3 fix cycles, with full context
7. **Observations — your call:** Every sprint-level observation left open (Step 8), listed verbatim from `review.md` with `file:line` + description. These never blocked the sprint; they are surfaced so the decision is yours. For each, you choose ACCEPT (merge as-is) or FIX (address in the worktree first).

**Do NOT filter, summarize, or editorialize review findings.** The user sees what the reviewer found and what the fixer did about it.

### User Decision

#### ACCEPT

Rebase the sprint branch onto current `<parent>` HEAD (in case `<parent>` advanced during the sprint), delete the sprint dir as the final commit, then fast-forward `<parent>` and clean up.

All of this runs **inside the worktree** — the session never reaches into the main checkout to switch its branch (that would disrupt your concurrent work on `<parent>`).

```bash
# Rebase onto current parent (we are already in the worktree).
git rebase <parent>                # halt with conflict report if it fails

# Final commit: remove the sprint dir.
git rm -r docs/sprints/<sprint>/
git commit -m "Sprint <sprint> complete"

# Fast-forward <parent> by ref, without checking it out anywhere.
if git push . <sprint-branch>:<parent>; then
    # Parent ref advanced. If the main checkout sits on <parent>, its index is now
    # behind its own ref — tell the user to `git reset --hard <parent>` (or `git pull .`)
    # there when convenient. Then clean up:
    git worktree remove <worktree>
    git branch -D <sprint-branch>
else
    # Refused: <parent> is checked out in the main checkout. Do NOT remove the
    # worktree — the user lands it from there. Surface exactly this:
    #   (in the main checkout)
    #   git checkout <parent> && git merge --ff-only <sprint-branch>
    #   git worktree remove <worktree> && git branch -D <sprint-branch>
    echo "HALT: <parent> is checked out in the main checkout; land it from there (see above)."
fi
```

If `git rebase <parent>` fails on conflicts, halt and surface the conflict. The user resolves in the worktree (`cd <worktree>; git status`), then re-runs ACCEPT.


#### FIX

Stay in the worktree. The user (or another `/implement-sprint` invocation, or a manual edit) addresses findings, re-commits inside the worktree, and the cycle continues. ACCEPT can be re-tried at any point.

There is no orchestrator-side FIX automation — issues identified in the final presentation may need human judgment that doesn't fit the implementer/reviewer protocol.

#### Abandoning a sprint (manual, no skill automation)

If a sprint goes sideways and you want to walk away:

```bash
git worktree remove --force <worktree>
git branch -D <sprint-branch>
# If parent_branch is the auto-created <sprint>-work and has zero useful commits:
git branch -D <sprint>-work
```

The skill never does this for you. RESET is not a path.

## Context Budget Summary

| What | Budget |
|------|--------|
| Orchestrator file reads | 2 files (spec + state.yaml) |
| Implementer prompt | Template only, no pasted content |
| Fixer prompt | Template + reviewer response verbatim |
| Reviewer prompt | Template only, no pasted content |
| Data-analyst prompt | Template only, no pasted content |
| Subagent result | Returned by the foreground Agent call — one blocking round-trip, never the `.output`/transcript |
| Implementer final response | < 2000 chars |
| Fixer final response | < 1500 chars |
| Reviewer final response | < 1500 chars |
| Data-analyst final response | < 1500 chars |

## Agent Summary

| Agent | Role | When | Execution |
|-------|------|------|-----------|
| **implementer** | Write code, tests, demos | Each phase | Foreground (long-running) |
| **implementer** (fixer) | Fix specific reviewer findings | After REVISIONS NEEDED | Foreground (long-running) |
| **reviewer** | Return structured verdict | After implement/fix | Foreground (fast) |
| the bundle's **`output-judge-agent`** | Verify output realism | After demos with output | Foreground (fast) |

All four agents receive a `Working directory: <worktree>` line at the top of their prompts. Agent definitions themselves are unchanged — they use absolute paths and are repo-root-agnostic.

## Failure Modes

**Pre-flight collision (worktree or branch already exists):** Halt. User cleans up the prior attempt manually.

**Test gate fails:** Report which test command, what error. User decides: fix in the worktree or abandon. (Pre-commit failures surface as reviewer `REVISIONS NEEDED` and go through the fix cycle.)

**Implementer overflows mid-phase ("Prompt is too long"):** the phase mixed too many work-shapes (source change + large existing-test migration + hand-rewrites) in one context. Do NOT retry the same single-implementer launch — it overflows again. STOP and report: the fix is in **planning** — re-classify the phase per create-sprint Step 6 and give it a `steps` block that decomposes it into fresh-context steps (`source → migrate → author`, with `migrate` defaulting to `tactic: fan-out`). A phase that mixes shapes with no `steps` block is the same planning gap.

**Fix cycle exhausted (3 cycles):** STOP automation. Report unresolved findings with full reviewer text. User decides: fix manually inside the worktree, accept the risk and ACCEPT anyway, or abandon.

**Sprint-review blocker loop exhausted (Step 8, 3 cycles):** STOP automation. Report the unresolved and `DISPUTED` *blockers* from `review.md`. Do NOT proceed to ACCEPT. (Observations never trigger this — they don't enter the loop; they're presented for the user's call.) User decides: fix manually inside the worktree, abandon, or — for a blocker that genuinely cannot be fixed — explicitly instruct that a `finding` note be filed. A note is never filed without that instruction.

**Demo crashes:** Report stack trace. User decides: fix or abandon.

**Data analyst finds anomalies:** Report findings. User decides: acceptable or not.

**Rebase conflict on ACCEPT:** Halt. User resolves in the worktree (`git status`, `git add`, `git rebase --continue`), then re-invokes ACCEPT.

## Tips

**For clean runs:**
- Ensure spec is unambiguous before starting
- Keep sprints small (less to merge back, less rebase conflict surface)
- Don't edit files in the worktree's package paths from the main checkout while the sprint runs — the worktree's venv won't see your edits anyway, but you may confuse yourself

**Concurrent sprints:**
- Each sprint gets its own worktree at `../worktrees/<name>` and its own `.venv`
- Two sprints from the same parent: whichever ACCEPTs first fast-forwards, the second one's ACCEPT rebases onto the new parent HEAD
- Two sprints from different parents: independent, no interaction

**If fix cycles keep failing:**
- The reviewer and fixer may disagree on approach — read the findings yourself to break the tie inside the worktree
