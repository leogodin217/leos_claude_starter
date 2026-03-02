---
name: implement-sprint
description: Automated sprint implementation with context discipline and quality gates.
disable-model-invocation: true
---

# Implement Sprint

Automated sprint implementation with context discipline and binding quality gates. Runs all phases without stopping, presents results for approval.

## Orchestrator Role

You are a **router**, not a judge. You launch agents, run automated gates, and relay results. You do NOT interpret technical findings or make quality decisions about code you haven't read.

**Binding rules:**

1. If a reviewer returns `VERDICT: REVISIONS NEEDED`, you MUST launch a fixer agent. You may NOT dismiss, reinterpret, or skip any finding.
2. If you disagree with a finding, include your disagreement alongside the finding in the final presentation. The user decides — you do not.
3. You never evaluate whether code is "intentional," "acceptable," or "a known pattern." Route findings; don't filter them.

## Prerequisites

- Sprint spec exists at `docs/sprints/current/spec.md`
- Sprint state at `docs/sprints/current/state.yaml`
- Contracts are fully defined (no ambiguity)

## Pre-Flight Checks

Run these checks before any implementation work. Do NOT skip or reorder them.

### 1. Git State

Run `git status`. If there are uncommitted changes:
- **Show the user** what files are modified/untracked
- **Ask the user** whether to proceed with those changes in place or stop
- **NEVER stash, checkout, or reset the user's changes.** Those changes may BE the sprint files. Destroying them destroys the sprint.

### 2. Spec Validation

After reading `spec.md` and `state.yaml`, verify the spec is current:
- The sprint name in `spec.md` should match `state.yaml`
- At least one phase should have status `pending`
- If the spec looks like a different/old sprint, **STOP and tell the user** rather than implementing the wrong thing

## Context Budget Rules

These rules prevent context exhaustion. Follow them exactly.

### Rule 1: Orchestrator Reads Minimally

You (the orchestrator) read ONLY these files:

| File | Purpose |
|------|---------|
| `docs/sprints/current/spec.md` | Sprint spec (required) |
| `docs/sprints/current/state.yaml` | Phase status (required) |

**Do NOT read source files, architecture docs, config models, or any `.py` file.** The implementer agent reads what it needs. Your job is orchestration, not comprehension.

### Rule 2: Subagent Prompts Are Brief

Pass to agents:
- Phase number and title (from spec)
- Sprint spec path: `docs/sprints/current/spec.md`
- One sentence summarizing the phase goal
- The quality/output rules block (standardized, see templates below)

**Do NOT paste code, file contents, contracts, or implementation details into prompts.** Exception: the fixer prompt includes the reviewer's response verbatim.

### Rule 3: TaskOutput — Never Double-Read

When calling TaskOutput for a subagent:
- Use `timeout: 600000` (10 minutes) on the FIRST call
- If it times out, call TaskOutput again with `timeout: 600000`
- **NEVER call TaskOutput on a subagent that already returned a result** — even partial

One TaskOutput call per subagent. Period.

### Rule 4: No Accumulation Between Phases

After committing a phase, you have the git history as your record. Do NOT retain mental summaries of what each phase did. The commit messages and state.yaml track progress.

Exception: retain the review verdict (APPROVED or list of unresolved findings) for the final presentation.

## Automation Model

```
/implement-sprint
       |
+------------------------------------------+
|  AUTOMATED (no human intervention)       |
|                                          |
|  For each phase:                         |
|    1. Implement (implementer agent)      |
|    2. Pre-commit                         |
|    3. Tests                              |
|    4. Review (reviewer agent)            |
|       ├─ APPROVED → step 6              |
|       └─ REVISIONS NEEDED               |
|          5. Fix cycle (max 3):           |
|             a. Fix (implementer agent)   |
|             b. Pre-commit + Tests        |
|             c. Re-review                 |
|          └─ 3 failures → STOP           |
|    6. Demo                               |
|    7. Analyze data (if applicable)       |
|    8. Commit                             |
|                                          |
|  After all phases:                       |
|    9. review-sprint                      |
|   10. Run all demos twice                |
|   11. Completion checks                  |
+------------------------------------------+
       |
+------------------------------------------+
|  PRESENT TO USER                         |
|                                          |
|  - Summary of what was built             |
|  - Test results + coverage               |
|  - Review findings + resolutions         |
|  - Demo output samples (both runs)       |
|  - Unresolved findings (if any)          |
+------------------------------------------+
       |
   User Decision
       |
+-------------+-------------+------------------+
|   ACCEPT    |    FIX      |     RESET        |
|             |             |                  |
| Keep        | Address     | git reset to     |
| commits     | issues,     | pre-sprint HEAD  |
|             | amend/fix   | Try again        |
+-------------+-------------+------------------+
```

**Key principle:** Commit after each phase for clean git history. Reset reverts all phase commits if needed.

## Process Details

### Phase Implementation (Automated)

For each phase in the sprint:

#### Step 1: Implement

Launch the **implementer** agent. Your prompt MUST follow this template exactly:

```
Implement Phase {N}: {Title} for the current sprint.

Sprint spec: docs/sprints/current/spec.md
Read the spec, focus on Phase {N}. Read source files as needed.

QUALITY RULES (mandatory):
- Decompose into module-level functions, not inner closures — helpers must be independently testable
- If two modules share logic, extract it into a shared module (DRY)
- Check every success criterion in the spec — missing deliverables (examples, configs) count as failures
- Use TYPE_CHECKING for type-only imports; keep runtime imports minimal
- Remove stale comments (sprint changelog comments, "# Future:", scaffolding markers)
- No code duplication — if you copy-paste and modify, extract a shared function instead
- Place tests in the module directory matching the code under test (e.g., tests/journeys/ for journey code). Never create sprint-named test files or a tests/sprints/ directory.

CODE NAVIGATION (mandatory — use LSP tools instead of Grep for code structure):
- find_definition: Jump to where a class/function is defined (not `Grep "def foo"` or `Grep "class Bar"`)
- find_references: Find all usages of a symbol (not `Grep "foo("` across directories)
- get_hover: Get type info/docs for a symbol without reading the whole file
- get_incoming_calls: Find what calls a function (not `Grep "function_name"`)
- find_workspace_symbols: Search for symbols by name across the codebase
- Reserve Grep for pattern searches (anti-patterns, TODOs, regex matching) — not for navigating code structure

OUTPUT RULES (mandatory):
- Final response MUST be under 2000 characters
- List files modified/created (paths only, no contents)
- Test result: pass count and fail count
- One-line summary per file change
- DECISIONS: List 1-3 key implementation decisions (where you placed code, which approach you chose, what you considered and rejected). One line each.
- Do NOT include code snippets, stack traces, or implementation details
- Do NOT re-read files you have already read
- If a demo fails after 3 attempts, report the error and stop

ITERATION LIMITS:
- Max 3 attempts to fix any single failing test
- Max 3 attempts to fix a demo script
- Never read the same file more than twice
```

**Do NOT add anything else to the prompt.** No file contents, no contracts, no code patterns.

Use `run_in_background: true`. Then call TaskOutput with `timeout: 600000`.

#### Step 2: Pre-commit

```bash
pre-commit run --all-files
```

**If pre-commit fails:** Fix issues yourself (these are usually formatting) and re-run. Do not launch a subagent for this.

#### Step 3: Tests

```bash
python -m pytest --cov=src/fabulexa --cov-fail-under=85
uv pip install -e .
```

**If tests fail:** Stop automation, report failure to user.

#### Step 4: Review

Launch the **reviewer** agent. Your prompt MUST follow this template:

```
Review Phase {N}: {Title} of the current sprint.

Sprint spec: docs/sprints/current/spec.md
Focus on Phase {N} only.

Check the changes for this phase:
  git diff HEAD

QUALITY CHECKS (in addition to standard review):
- Are helpers module-level functions (not closures/nested defs)?
- Any code duplication over 10 lines?
- Any success criteria from the spec not delivered?
- Any runtime imports that should be TYPE_CHECKING only?
- Any stale sprint comments left in modified files?
- Does the implementation stay within Phase {N} scope? Flag any code that belongs to a different phase.

CODE NAVIGATION: Use mcp__cclsp__find_definition and find_references to trace code paths. Do not Grep for "def foo" or "class Bar" — use LSP tools instead.

OUTPUT FORMAT (mandatory — follow exactly):

VERDICT: APPROVED

or

VERDICT: REVISIONS NEEDED
FINDINGS:
- [file:line] description of required change
- [file:line] description of required change

Final response MUST be under 1500 characters.
Use ONLY the verdict format above. No prose before the verdict line.
```

Use `run_in_background: false` (reviewer is fast).

**Routing (mechanical — no interpretation):**

| Verdict | Action |
|---------|--------|
| `VERDICT: APPROVED` | Proceed to Step 6 (Demo) |
| `VERDICT: REVISIONS NEEDED` | Proceed to Step 5 (Fix Cycle) |

You do NOT evaluate whether findings are valid. You read the verdict and route.

#### Step 5: Fix Cycle

When the reviewer returns `VERDICT: REVISIONS NEEDED`, launch the **implementer** agent:

```
Fix review findings for Phase {N}: {Title}.

Sprint spec: docs/sprints/current/spec.md
Read the spec for Phase {N} context, then fix the findings below.

REVIEWER FINDINGS (must be addressed):
{paste the reviewer's full response verbatim — do not summarize or filter}

RULES:
- Address every finding listed above
- If a finding is genuinely incorrect, state DISPUTED with a one-line reason — do NOT silently skip it
- Run tests after fixes to verify nothing breaks
- Do not make changes beyond what the findings require
- Use LSP tools (find_definition, find_references, get_incoming_calls) to navigate code — not Grep for definitions/references

OUTPUT RULES (mandatory):
- Final response MUST be under 1500 characters
- For each finding: FIXED or DISPUTED (with one-line reason)
- List files modified (paths only)
- Test result: pass count and fail count
```

Use `run_in_background: true`. Then call TaskOutput with `timeout: 600000`.

After the fixer completes:

1. Run pre-commit (Step 2)
2. Run tests (Step 3)
3. Re-launch reviewer (same prompt as Step 4)

**Max 3 fix cycles per phase.** After 3 cycles still returning `REVISIONS NEEDED`:
- STOP automation
- Do NOT commit the phase
- Collect the unresolved findings for the final presentation
- Report to user immediately

#### Step 6: Demo

```bash
python docs/sprints/current/demos/phase_N_*.py
```

Demo must run without errors and exit 0.

#### Step 7: Analyze Data (If Applicable)

If the demo produces simulation output, launch the **data-analyst** agent:

```
Analyze output from Phase {N} demo.

Demo script: docs/sprints/current/demos/phase_{N}_*.py
Run the standard validation workflow from your instructions.

OUTPUT RULES (mandatory):
- Final response MUST be under 1500 chars
- Use VALIDATION: PASS or VALIDATION: ISSUES FOUND format
```

#### Step 8: Commit Phase

Update state.yaml to show status.

```bash
git add -A
git commit -m "$(cat <<'EOF'
Sprint [Name] - Phase N: [Title]

- [What this phase implemented]
- Tests: PASS
- Pre-commit: PASS
- Review: APPROVED [or: APPROVED after N fix cycles]

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### Step 8b: Attach Sprint Notes

After the commit succeeds, attach a structured note to the commit. This provides cross-session context for reviewers and future implementers.

Build a JSON object from data you already have (implementer summary, reviewer verdict, fix cycle count). Then attach it:

```bash
git notes --ref refs/notes/agent/sprint add -m "$(cat <<'EOF'
{
  "sprint": "[Name]",
  "phase": N,
  "decisions": [
    "[from implementer DECISIONS output — 1-3 lines]"
  ],
  "review_cycles": N,
  "findings_fixed": ["[from fixer output, if any]"],
  "findings_disputed": ["[from fixer output, if any]"],
  "files_created": ["[from implementer output]"],
  "files_modified": ["[from implementer output]"]
}
EOF
)" HEAD
```

**Schema rules:**
- `decisions`: Key implementation choices from the implementer's DECISIONS output. Copy verbatim — do not summarize.
- `review_cycles`: Integer. 0 if reviewer approved first pass.
- `findings_fixed` / `findings_disputed`: Empty arrays `[]` if reviewer approved first pass.
- `files_created` / `files_modified`: From the implementer's file list.

**If the git notes command fails** (e.g., git notes not available), log a warning and continue. Notes are supplementary — never block the sprint on them.

### Post-Implementation (Automated)

After all phases complete:

#### Step 9: Review Sprint

Run `/review-sprint` for comprehensive fresh-eyes audit.

#### Step 10: Run All Demos Twice

```bash
for demo in docs/sprints/current/demos/phase_*.py; do
    python "$demo"
done

for demo in docs/sprints/current/demos/phase_*.py; do
    python "$demo"
done
```

Both runs must produce consistent output.

#### Step 11: Completion Checks

```bash
pre-commit run --all-files
git status --porcelain | grep "^??"
grep -rn "# Future:" src/
grep -rn "pass$" src/
```

### Present to User

Show:
1. **Summary:** What was built, files changed
2. **Tests:** Pass/fail count, coverage percentage
3. **Review findings:** For each phase, list all reviewer findings and their resolution (FIXED, DISPUTED, or UNRESOLVED). Include the reviewer's original text — do not paraphrase.
4. **Demos:** Sample output proving it works
5. **Unresolved items:** Any findings that survived 3 fix cycles, with full context

**Do NOT filter, summarize, or editorialize review findings.** The user sees what the reviewer found and what the fixer did about it.

### User Decision

#### ACCEPT

Commits already made per-phase. Update state.yaml and archive sprint.

#### FIX

1. Fix the specific issues
2. Run pre-commit
3. Commit the fix
4. Re-run review-sprint
5. Present again

#### RESET

```bash
git log --oneline -10
git reset --hard <pre-sprint-commit>
git clean -fd
```

## Context Budget Summary

| What | Budget |
|------|--------|
| Orchestrator file reads | 2 files (spec + state.yaml) |
| Implementer prompt | Template only, no pasted content |
| Fixer prompt | Template + reviewer response verbatim |
| Reviewer prompt | Template only, no pasted content |
| Data-analyst prompt | Template only, no pasted content |
| TaskOutput calls per subagent | Exactly 1 |
| TaskOutput timeout | 600000ms (10 min) |
| Implementer final response | < 2000 chars |
| Fixer final response | < 1500 chars |
| Reviewer final response | < 1500 chars |
| Data-analyst final response | < 1500 chars |

## Agent Summary

| Agent | Role | When | Background |
|-------|------|------|------------|
| **implementer** | Write code, tests, demos | Each phase | Yes (600s timeout) |
| **implementer** (fixer) | Fix specific reviewer findings | After REVISIONS NEEDED | Yes (600s timeout) |
| **reviewer** | Return structured verdict | After implement/fix | No (foreground) |
| **data-analyst** | Verify output realism | After demos with output | No (foreground) |

## Failure Modes

**Gate fails (pre-commit/tests):** Report which gate, what error. User decides: fix or reset.

**Fix cycle exhausted (3 cycles):** STOP automation. Report the unresolved findings with full reviewer text. User decides: fix manually, accept the risk, or reset.

**Demo crashes:** Report stack trace. User decides: fix or reset.

**Data analyst finds anomalies:** Report findings. User decides: acceptable or not.

## Tips

**For clean runs:**
- Ensure spec is unambiguous before starting
- Use a dedicated branch for risky sprints
- Keep sprints small (easier to reset)

**If you keep resetting:**
- The spec may be flawed (ambiguous, contradictory)
- Consider running `/create-sprint` again
- Or manually implement the tricky part first

**If fix cycles keep failing:**
- The reviewer and fixer may disagree on approach — this needs human judgment
- Read the findings yourself to break the tie
