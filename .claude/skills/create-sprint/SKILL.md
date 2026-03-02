---
name: create-sprint
description: Guide sprint planning from scope assessment to spec artifacts.
disable-model-invocation: true
---

# Plan Sprint

This command guides the sprint planning process.

## Process

### 1. Assess Current State

Load and review:
- `docs/CAPABILITIES.md` - What the system should do (includes status per capability)
- `docs/architecture/README.md` - Implementation status by module

Identify gaps: What capabilities are not started or partial?

### 2. Propose Sprint Scope

Based on gaps and dependencies, propose what this sprint should deliver.

**Scope can be:**
- Part of one capability (e.g., "generated actors only, not arrivals")
- Parts of multiple capabilities (e.g., "basic actors + basic entities needed together")
- Infrastructure that enables capabilities (e.g., "config parsing before anything else")

Write a scope proposal:
```markdown
## Proposed Scope

**Delivers:** [What this sprint produces]

**Capabilities touched:**
- actors: generated actors, properties (not arrivals, not lifecycle)
- entities: generated entities, properties

**Rationale:** [Why this scope makes sense—dependencies, complexity, coherence]

**Not included:** [What's explicitly deferred]
```

Present scope to user for approval before proceeding.

### 3. Load Detailed Context

Once scope is approved, load relevant docs:
- `docs/architecture/README.md` - See reading order for which docs to load
- `docs/architecture/*.md` - Design rationale and constraints
- `docs/architecture/pending/*.md` - Design doc for this feature (if one exists)

If a design doc exists in `pending/`, extract contracts from it. The design doc provides rationale and semantics (the WHY). The sprint spec provides contracts, phases, and test cases (the WHAT). Do not duplicate prose from the design doc — reference it.

### 4. Define Purpose and Success Criteria

Write a clear purpose statement:
- One sentence describing what this sprint delivers
- How an educator will use this capability
- Observable success criteria

### 5. Design Contracts

Use the **architect** agent to design interface contracts.

Each contract needs:
- Full function signature with type hints
- Complete docstring (Args, Returns, Raises)
- NO default parameters (Principle #7)
- NO scaffolding for future work (Principle #8)
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

Divide work into independently testable phases:

| Phase | Delivers | Demo Proves |
|-------|----------|-------------|
| 1 | Core functionality | Basic operation works |
| 2 | Extended features | Full capability works |
| N | Integration | End-to-end works |

Each phase must:
- Be independently testable
- Have a standalone demo script
- List explicit test cases (not just test files)
- Build on previous phases

### 7. Define Demo Requirements

Demo scripts live in `docs/sprints/current/demos/`.

For each phase, specify:
- What the demo script demonstrates
- Sample config (embedded in demo)
- Expected output/behavior
- Success criteria

### 8. Create Artifacts

**Create `docs/sprints/current/spec.md`:**
```markdown
# Sprint: [Name]

## Purpose
[One sentence + educator use case]

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

**Files:**
| Action | File |
|--------|------|
| Modify | `packages/<pkg>/src/<module>.py` |
| Create | `packages/<pkg>/tests/<module>/test_<name>.py` |

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

Quick-reference table of all files touched across all phases:

| File | Change |
|------|--------|
| `path/to/file.py` | One-line summary of change |
```

**Update `docs/sprints/current/state.yaml`:**
```yaml
sprint: sprint-name
started: YYYY-MM-DD
current_phase: 1
capabilities:
  - actors: [generated, properties]
  - entities: [generated, properties]
phases:
  1: {status: pending}
  2: {status: pending}
```

### 9. Update Status

After sprint completes:
- Update `docs/CAPABILITIES.md` status markers for touched capabilities
- Update `docs/architecture/README.md` Implementation Status table if modules changed
- Archive sprint to `docs/sprints/archive/`

## Quality Checks Before Done

- [ ] Scope approved by user
- [ ] Purpose is clear and educator-focused
- [ ] Capabilities touched are explicit
- [ ] Breaking changes documented (or section omitted if purely additive)
- [ ] All contracts have full signatures + docstrings
- [ ] NO default parameters in any contract (Principle #7)
- [ ] NO scaffolding for future work (Principle #8)
- [ ] NO implementation code in contracts (signatures and docstrings only)
- [ ] Anti-scaffolding checklist passed
- [ ] Phases are independently testable
- [ ] Each phase has explicit test case bullets (not just file names)
- [ ] Demo requirements specified per phase
- [ ] "What Doesn't Change" section present
- [ ] Module Changes Summary present
- [ ] spec.md created
- [ ] state.yaml updated

## Code Navigation

When exploring existing code during planning, use LSP tools instead of Grep for structural queries:

| Task | Use | Not |
|------|-----|-----|
| Find where a class/function is defined | `find_definition` | `Grep "def foo"` |
| Find all callers/usages of a symbol | `find_references` | `Grep "foo("` across dirs |
| Get type info without reading whole file | `get_hover` | `Read` entire file |
| Find what calls a function | `get_incoming_calls` | `Grep "function_name"` |
| Search for symbols by name | `find_workspace_symbols` | `Glob` + `Grep` |

Reserve Grep for pattern searches (anti-patterns, TODOs, regex matching).

## When to Use Architect Agent

Invoke the **architect** agent when you need to:
- Design complex interfaces
- Make architectural decisions
- Update architecture docs
- Resolve design ambiguities
