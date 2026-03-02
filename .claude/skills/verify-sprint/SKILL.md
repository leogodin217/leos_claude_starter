---
name: verify-sprint
description: Spec-fidelity verification tracing requirements through code.
disable-model-invocation: true
---

# Verify Sprint

Spec-fidelity review. Walk the spec's algorithms and requirements step-by-step, verify the code implements each one correctly. Find behavioral bugs that mechanical checks miss.

## When to Use

After `/review-sprint` passes. That command checks surface properties (coverage, linting, dead code). This command checks **behavioral correctness** — does the code actually do what the spec says?

## What This Is NOT

- Not a linter check (use `/review-sprint`)
- Not a docs-vs-code audit (use `/arch-review`)
- Not a test quality review (use `/review-tests`)

This is the review that asks: "If I follow the spec's algorithm with a pencil, does the code do the same thing at every step?"

## Context to Load

1. `CLAUDE.md` — Principles (especially #7, #8)
2. Architecture doc for the feature (e.g., `docs/architecture/pending/*.md`)
3. `docs/sprints/current/spec.md` — Contracts and phase breakdown
4. All new/modified source files (`git diff --name-only main..HEAD -- '*.py' ':!tests/' ':!demos/'`)
5. Test files for new source files

Load the architecture doc FIRST. Read it completely before touching any code. The spec is the oracle.

**Code navigation:** Use LSP tools for all code tracing — `find_definition` to jump to implementations, `find_references` to find usages, `get_incoming_calls` to trace call chains, `get_hover` for type info. Do not Grep for `def foo` or `class Bar`. Reserve Grep for pattern searches only.

## Review Process

### 1. Extract Spec Requirements

Read the architecture doc and sprint spec. Extract every behavioral requirement into a checklist. Categories:

**Algorithm steps:** Numbered steps in resolution/processing algorithms. Each step is a requirement.

**Branching logic:** "If X then Y, else Z" — each branch is a requirement.

**Timestamp/RNG semantics:** Which distribution, what parameters, what order of RNG consumption.

**Error conditions:** What raises, when, with what message.

**Feature interactions:** How the new feature interacts with existing features (events, re-entry, mutations, deactivation).

**Invariants:** Properties stated as "always true" in the spec.

Write each requirement as a one-line checklist item with a spec citation:

```
- [ ] Step 6i: Terminal state behaviors fire after transition recorded (architecture doc line N)
- [ ] Dropout behaviors use sequential exponential gaps, not uniform (Behaviors section)
- [ ] Runtime probability sum > 1.0 raises SimulationError (Algorithm step 4)
```

### 2. Trace Each Requirement Through Code

For EACH checklist item:

1. Find the corresponding code path
2. Read the code line by line
3. Verify behavioral equivalence (not just structural presence)
4. Check: does the code handle the same edge cases the spec describes?

**Critical distinction:** "Code exists for this feature" is NOT the same as "code correctly implements this feature." A function that handles transitions may still use the wrong selection algorithm.

### 3. Identify Untested Spec Requirements

For each requirement verified in step 2, check if a test exercises it:

1. Search test files for the specific behavior
2. Verify the test actually triggers the code path (not just nominally testing it)
3. Flag requirements that have NO test coverage

Common gaps:
- Terminal state behaviors (tests often stop at "reached terminal")
- Dropout-specific behavior (tests check dropout happened, not HOW)
- Timestamp algorithm differences between code paths
- RNG consumption order
- Edge cases mentioned in spec but not in tests

### 4. Check Code Quality at Boundaries

Look specifically at:

**Encapsulation:** Does new code use public APIs or reach into private attributes?

**Precision:** Are numeric conversions lossy? (float→int, timedelta→seconds)

**Floating point:** Are equality/comparison checks on accumulated floats safe?

**Duplication:** Is the same logic implemented twice with slight variations? (Often indicates a missed abstraction or a branch that should dispatch to different implementations.)

### 5. Assess Test-Spec Alignment

For each test:
1. What spec requirement does it claim to test?
2. Does it actually exercise that requirement's code path?
3. Would the test still pass if the requirement were implemented wrong?

A test that passes by accident (wrong layer, wrong code path, insufficient assertions) is worse than no test — it creates false confidence.

## Output Format

Structure findings as:

```markdown
# Sprint Verification: [Name]

**Date:** YYYY-MM-DD
**Spec:** [path to architecture doc]
**Sprint:** [path to sprint spec]

## Requirements Checklist

### Algorithm Steps
- [x] Step 1: Description — VERIFIED (file:line)
- [ ] Step 6i: Terminal behaviors — MISSING (code returns before evaluation)
- [x] Step 5: Weighted selection — VERIFIED (file:line)

### Feature Interactions
- [x] Mutations visible to subsequent states — VERIFIED
- [ ] Events frozen at entry tick — NOT TESTED

### Invariants
- [x] Deterministic — VERIFIED (test exists)
- [x] Monotonic timestamps — VERIFIED

## Findings

### Bug: [Title]

**Spec says:** [Quote from spec with section reference]
**Code does:** [What actually happens, with file:line]
**Impact:** [What breaks for educators/students]
**Test gap:** [Why existing tests don't catch this]

### Code Quality: [Title]

**Location:** file:line
**Issue:** [Description]
**Severity:** High / Medium / Low

## Summary

| Category | Total | Verified | Missing | Wrong |
|----------|-------|----------|---------|-------|
| Algorithm steps | N | N | N | N |
| Feature interactions | N | N | N | N |
| Invariants | N | N | N | N |
| Error conditions | N | N | N | N |

**Verdict:** [PASS / ISSUES FOUND]
```

## Principles

- **Spec is oracle.** If code differs from spec, it's a bug until proven otherwise. If the code is genuinely better, note it as a spec update candidate — but still flag it.
- **Behavioral equivalence, not structural.** Don't just check "there's a function for X." Check that the function does X correctly.
- **Negative space matters.** Requirements the tests DON'T cover are the highest-risk findings.
- **One finding per deviation.** Don't bundle. Each spec deviation is its own finding with its own citation.
- **No opinions on style.** This review is about correctness, not aesthetics. Leave style to `/review-sprint`.
