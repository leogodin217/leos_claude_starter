---
name: review-sprint
description: Post-implementation mechanical audit of sprint deliverables.
---

# Review Sprint

Post-implementation review with fresh eyes. Run after implement-sprint completes.

## Purpose

Catch issues that slip through when implementer is too close to the code:
- Dead code and scaffolding
- Test names that don't match test behavior
- Spec-implementation drift
- Uncovered error paths

## Context Loading (Minimal)

Load ONLY:
1. `CLAUDE.md` - Principles (especially #7 and #8)
2. `docs/sprints/current/spec.md` - What was planned
3. Changed files this sprint (use git diff)
4. Test files for changed code

**DO NOT load:**
- Full architecture docs
- Historical context
- Capability docs

Fresh eyes means deliberately ignorant of the "why" — only checking the "what."

## Review Process

### 1. Dead Code Scan

```bash
# Find scaffolding patterns
grep -rn "# Future:" src/
grep -rn "# TODO:" src/
grep -rn "pass$" src/

# Find unused variables (requires manual review)
# Look for: assigned but never read, precomputed but not used
```

**Flag:** Any loop body that only contains `pass`, `continue`, or comments.

**Flag:** Any `__init__` that stores data not used by other methods.

### 2. Test Name Audit

For each test file changed this sprint:

1. Read test function name
2. Read test docstring
3. Read test body
4. **Verify:** Does the test actually test what the name claims?

Common lies:
- `test_X_order` that doesn't verify ordering
- `test_X_deterministic` that only runs once
- `test_X_error` that doesn't verify the error type/message

### 3. Coverage Analysis

```bash
# Get coverage for new files only
pytest --cov=src/fabulexa --cov-report=term-missing

# Check files added this sprint
git diff --name-only --diff-filter=A main...HEAD
```

**Flag:** Any new file with < 100% coverage.

**Flag:** Uncovered lines that are error conditions (even if "shouldn't happen").

### 4. Spec-Implementation Comparison

#### 4a. Load Sprint Notes (if available)

Read implementation decisions attached to phase commits:

```bash
# Find sprint commits and read their notes
for sha in $(git log --oneline --grep="Sprint" | head -10 | awk '{print $1}'); do
    echo "=== $sha ==="
    git notes --ref refs/notes/agent/sprint show "$sha" 2>/dev/null || echo "(no notes)"
done
```

If notes exist, use the `decisions` field to understand **why** the implementer made specific choices. This enables checking intent-vs-implementation, not just spec-vs-implementation.

#### 4b. Compare Contracts

For each contract in spec.md:
1. Find the implementation
2. Compare signature (params, types, return)
3. Compare docstring (Args, Returns, Raises)
4. Note any improvements or divergences
5. If sprint notes recorded a decision about this contract, verify the stated rationale matches the code

**Document:** If implementation is better than spec, note it for spec update.

**Flag:** If implementation is worse than spec, it's a bug.

**Flag:** If a noted decision contradicts the spec without justification, it's a deviation.

### 5. Workspace Check

```bash
git status --porcelain
```

**Flag:** Any untracked files that aren't in .gitignore.

### 6. Pre-commit Compliance

```bash
pre-commit run --all-files
```

**Flag:** Any pre-commit failure (formatting, linting, type errors).

### 7. Demo Verification

Run all demo scripts twice to verify determinism and consistency:

```bash
# First run
for demo in docs/sprints/current/demos/phase_*.py; do
    python "$demo"
done

# Second run
for demo in docs/sprints/current/demos/phase_*.py; do
    python "$demo"
done
```

**Flag:** Any demo that fails or produces different output between runs.

## Output Format

Create review report in `docs/sprints/current/review.md`:

```markdown
# Sprint Review: [Name]

**Date:** YYYY-MM-DD
**Reviewer:** Claude (fresh eyes)

## Summary

| Check | Status | Issues |
|-------|--------|--------|
| Dead code | PASS/FAIL | N issues |
| Test names | PASS/FAIL | N issues |
| Coverage | PASS/FAIL | N files < 100% |
| Spec sync | PASS/FAIL | N divergences |
| Workspace | PASS/FAIL | N artifacts |
| Pre-commit | PASS/FAIL | N failures |
| Demos | PASS/FAIL | N failures |

## Issues Found

### 1. [Issue Title]

**Category:** Dead code / Test name / Coverage / Spec sync / Workspace / Demos
**Location:** file:line
**Problem:** [What's wrong]
**Action:** [What to do]

---

## Recommendation

[ ] APPROVED - No blocking issues
[ ] REVISIONS NEEDED - Fix issues and re-review
```

## When to Use

Run review-sprint:
- After all phases of implement-sprint complete
- Before `/verify-sprint`
- When you suspect quality issues

## Review Pipeline

This command checks **mechanical** properties. Follow it with `/verify-sprint` for **behavioral** correctness.

```
implement-sprint (per phase)
    └── reviewer agent (quick check)

review-sprint (after all phases)
    └── mechanical audit: coverage, linting, dead code, test names

verify-sprint (after review-sprint passes)
    └── spec-fidelity audit: does code match spec's algorithms step-by-step?
```

`/review-sprint` catches sloppy code. `/verify-sprint` catches correct-looking code that does the wrong thing. Both must pass before merge.

## Agent Instructions

When invoked, use the **reviewer** agent with these specific instructions:

1. Load minimal context (see above)
2. Run all 7 checks systematically
3. Document ALL findings (not just blockers)
4. Be skeptical — assume issues exist until proven otherwise
5. Produce the review report
6. Use LSP tools for code navigation — `find_definition` / `find_references` / `get_incoming_calls` to trace code, not Grep for definitions or call sites

The reviewer should NOT:
- Assume the implementer was right
- Skip checks because "it passed CI"
- Accept "it works" as proof of quality
- Grep for `def foo` or `class Bar` — use `find_definition` instead
- Grep a function name across directories to find callers — use `find_references` or `get_incoming_calls`
