---
name: eval-sprint
description: Adversarial evaluation of sprint spec before implementation.
disable-model-invocation: true
---

# Evaluate Sprint Spec

Adversarial evaluation of sprint spec before implementation. Run in a **new session** to ensure fresh eyes.

## Purpose

Find problems in the spec that would cause implementation to fail or produce poor results. The evaluator is deliberately adversarial — looking for ways the spec could be misinterpreted, is incomplete, or violates principles.

## Context posture

**Deliberately minimal — do NOT run `/understand`, and do NOT load architecture
docs.** This is load-bearing, not an oversight. The question this skill answers
is whether an implementer could build from the spec *alone*; anything you learn
from an architecture doc is something the spec failed to say, and reading it
hides the gap instead of reporting it. Any later edit that adds an architecture
load here removes the thing the skill is for.

Load ONLY:
1. `CLAUDE.md` — Principles — especially no-invented-values and no-future-scaffolding. Already in context.
2. `docs/sprints/<sprint-name>/spec.md` — The spec to evaluate

**DO NOT load:**
- Architecture docs and capability docs (see above)
- Previous conversation context (that's why new session)
- **Source files via Read** — use LSP tools instead (see below).

## Code Verification — LSP Only

When verifying spec claims against the codebase (class names, function signatures, caller counts, line numbers), use **only LSP tools**. Do NOT read entire source files — this wastes context on code irrelevant to the evaluation.

| Verification need | LSP tool | Example |
|---|---|---|
| "Does this class/function exist?" | `find_definition` | Spec says `TypeResolver` — verify the actual class name |
| "Who calls this function?" | `find_references` | Spec says "only two callers" — verify caller count |
| "What's the signature?" | `get_hover` | Spec says `rng` param at line 203 — verify |
| "What type is this?" | `get_hover` | Spec references `Distribution` union — verify it exists |
| "Does this symbol exist in the module?" | `find_workspace_symbols` | Spec says export from `__init__.py` — verify |
| "Who calls this / what does it call?" | `get_incoming_calls` / `get_outgoing_calls` | Spec claims a caller count or call chain — trace it across module and package boundaries |

**NEVER** use `Read` on source files for this skill. If you catch yourself about to read a `.py` file, use an LSP tool instead.

## Evaluation Checklist

### Structural Checks
- [ ] Every phase has: Delivers, Demo, Contracts sections
- [ ] Every contract has: full signature with types
- [ ] Every contract has: docstring with Args, Returns, Raises
- [ ] Success criteria are checkboxes (testable)
- [ ] Scope lists what's NOT included
- [ ] File structure section shows where code goes

### Principle Checks
- [ ] No default parameters in any signature (the no-invented-values principle)
- [ ] No `= None`, `= []`, `= {}` in signatures (the no-invented-values principle)
- [ ] No "Future:", "TODO:", "placeholder", "stub" language (the no-future-scaffolding principle)
- [ ] No loops/iterations described that "will do X later" (the no-future-scaffolding principle)
- [ ] No hardcoded domain values in contracts (the no-hardcoded-domains principle)

### Consistency Checks
- [ ] All types referenced in contracts exist (in spec or codebase)
- [ ] All functions called in demos are defined (in spec or codebase)
- [ ] Phase N only uses contracts from phases 1..N (dependency order)
- [ ] Stated scope matches contracts (nothing extra, nothing missing)
- [ ] Contract names follow existing codebase conventions

### Ambiguity Checks
- [ ] No weasel words: "appropriate", "as needed", "etc.", "various", "properly"
- [ ] No vague verbs: "handle", "process", "manage" without specifics
- [ ] Error conditions are specific (not just "raises Exception")
- [ ] Return types are concrete (not "suitable value")
- [ ] None/empty input behavior is specified
- [ ] Edge cases appear in Raises section

### Testability Checks
- [ ] Each contract has at least one obvious test case
- [ ] Demo requirements are specific enough to automate
- [ ] Success criteria are measurable (not "works correctly")
- [ ] Can write a test that would FAIL if contract is wrong

### Architecture Checks
- [ ] New code doesn't break existing interfaces
- [ ] Module placement matches existing structure
- [ ] Naming follows existing conventions
- [ ] No circular dependencies introduced

## Evaluation Process

### Step 1: Read Spec Cold

Read the entire spec without referring to other docs. Note:
- What's confusing?
- What questions do you have?
- What seems underspecified?

### Step 2: Run Checklist

Go through each check systematically. For every failure:
- Note the location (section, line if possible)
- Describe the problem specifically
- Suggest a fix

### Step 3: Adversarial Questions

For each contract, ask:
- "What's the worst reasonable misinterpretation?"
- "What input would break this?"
- "What if I implemented this lazily/wrong — would tests catch it?"

### Step 4: Dependency Trace

Trace through phases in order:
- Phase 1: What does it need? (should be nothing or existing code)
- Phase 2: What does it need from Phase 1? Is that actually delivered?
- Continue for all phases

### Step 5: Demo Feasibility

For each demo:
- Can I actually write this with the contracts provided?
- Does it prove what it claims to prove?
- What could pass the demo but still be wrong?

## Output Format

```markdown
# Spec Evaluation: [Sprint Name]

**Verdict: PASS / NEEDS WORK / FAIL**

**Summary:** [One sentence assessment]

---

## Blocking Issues

Issues that MUST be fixed before implementation.

### 1. [Short Title]

**Location:** [Section/line reference]
**Category:** [Structural/Principle/Consistency/Ambiguity/Testability/Architecture]
**Problem:** [Specific description]
**Impact:** [What goes wrong if not fixed]
**Suggested Fix:** [How to fix it]

---

## Warnings

Issues that SHOULD be addressed but aren't blocking.

### 1. [Short Title]

**Location:** [Section/line reference]
**Problem:** [Description]
**Suggestion:** [How to improve]

---

## Notes

Observations that aren't issues but worth considering.

- [Note 1]
- [Note 2]

---

## Checklist Results

| Category | Pass | Fail | Issues |
|----------|------|------|--------|
| Structural | 5 | 1 | Missing file structure |
| Principles | 4 | 0 | — |
| Consistency | 3 | 1 | Undefined type |
| Ambiguity | 3 | 2 | Weasel words |
| Testability | 3 | 0 | — |
| Architecture | 4 | 0 | — |

---

## Verdict Explanation

**PASS:** No blocking issues. Warnings are minor. Spec is ready for implementation.

**NEEDS WORK:** No blocking issues but warnings are significant. Review before proceeding.

**FAIL:** Blocking issues found. Must fix and re-evaluate before implementation.
```

## Verdicts

### PASS
- Zero blocking issues
- Warnings are cosmetic or minor
- Checklist mostly green
- Confident implementation will succeed

### NEEDS WORK
- Zero blocking issues
- But significant warnings that could cause problems
- User should review warnings before proceeding
- Implementation might need course correction

### FAIL
- One or more blocking issues
- Spec is incomplete, contradictory, or violates principles
- Must fix and run eval-sprint again
- Do NOT proceed to implement-sprint

## Common Blocking Issues

| Issue | Why It Blocks |
|-------|---------------|
| Missing contract for stated scope | Implementer won't know what to build |
| Undefined type referenced | Code won't compile |
| Default parameter in signature | No-invented-values violation |
| Phase dependency violation | Phase N can't be built |
| Ambiguous return type | Implementer will guess wrong |

## Common Warnings

| Issue | Why It's a Warning |
|-------|-------------------|
| Vague error message | Implementation will work but be unhelpful |
| Missing edge case | Might cause bug but not blocking |
| Inconsistent naming | Annoying but not fatal |
| Demo doesn't fully exercise contract | Partial verification |

## After Evaluation

- **If PASS:** Proceed to `/implement-sprint`
- **If NEEDS WORK:** Review warnings, decide to proceed or fix
- **If FAIL:** Fix blocking issues, run `/eval-sprint` again

## Tips for Evaluators

1. **Be skeptical** — Assume the spec has problems until proven otherwise
2. **Read literally** — Don't fill in gaps with what you think they meant
3. **Think like a lazy implementer** — What's the minimal interpretation?
4. **Think like a malicious implementer** — What technically satisfies the spec but is wrong?
5. **Check the edges** — Empty lists, None values, zero counts, boundary conditions
