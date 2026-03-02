---
name: arch-review
description: Review architecture documents against code implementation and principles.
disable-model-invocation: true
---

# Architecture Review

Review architecture documents against implementation and principles.

## Context to Load

1. `CLAUDE.md` - Core principles
2. `docs/architecture/README.md` - Architecture overview, implementation status
3. Architecture docs being reviewed (user specifies or all in `docs/architecture/`)
4. Relevant implementation code in `src/fabulexa/`

## Process

### Phase 1: Analysis

**Code navigation:** Use LSP tools for code exploration — `find_definition` to locate implementations, `find_references` to trace usages, `get_hover` for type info. Do not Grep for `def foo` or `class Bar`.

1. Read all specified architecture docs
2. Read corresponding implementation code
3. Compare design vs implementation
4. Identify issues in these categories:
   - **Mismatch**: Doc says X, code does Y
   - **Missing spec**: Doc references undefined behavior
   - **Inconsistency**: Docs contradict each other
   - **Design question**: Valid approaches, needs decision

### Phase 2: Document Issues

Create or update `docs/SCRATCHPAD.md` with:

```markdown
# Architecture Review Scratchpad

## Issues to Resolve

### 1. [Short title]

**Status:** Open

**Location:** [file:line or section reference]

**Problem:** [What's wrong]

**Options:** [If design question, list options A/B/C]

---

## Resolved Issues

### N. [Short title]

**Resolution:** [What was decided]

**Decision:** [Rationale and changes made]

---
```

### Phase 3: Resolution Loop

For each issue:

1. **Present** the issue with context
2. **Analyze** options if it's a design question
3. **Wait for user decision** - DO NOT change docs until user approves
4. **Make changes** after approval
5. **Update scratchpad** - move to Resolved with decision rationale

### Phase 4: Completion

Review is complete when:
- All issues resolved, OR
- Only nitpicky issues remain (formatting, minor wording)

If significant issues found → user may request another review round.

## Key Principles

- **Code is truth** after implementation - docs point to code, not duplicate
- **Evaluate which is better** - don't blindly sync doc to code or vice versa
- **Agree before changing** - get user decision before modifying docs
- **Document rationale** - future readers need to know WHY

## Output

After each round, summarize:
- Issues found: N
- Resolved: N
- Remaining: N (with brief list)

## Example Usage

User: "Review simulation.md and actors.md"
→ Load docs, analyze, create scratchpad, present first issue, wait for decision
