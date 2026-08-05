---
status: draft
---

# Feature Name

A pending architecture doc describing a specific change to the system. Lives at
`docs/architecture/pending/<name>.md`.

The sections below are a flat list — no zones. `Affected Subsystems` is the
prose description of which subsystems the change touches; there is no
frontmatter scope declaration.

---

## Problem

What's wrong or missing. Include a concrete example: config snippet showing the
limitation, error message, or workflow that doesn't work.

## Solution

High-level approach. One paragraph describing the design direction, plus a
diagram or YAML snippet showing the end state.

## Affected Subsystems

Name the subsystems / packages this design touches and describe the
*behavioral or contract* change each one undergoes. No file paths, no line
ranges, no import tables, and no references to which sibling architecture-doc
sections will be rewritten — production docs are updated after implementation,
separately from this design.

- **Subsystem A** — what changes about its contract or behavior.
- **Subsystem B** — what new dependency or invariant it picks up.

## What Doesn't Change

Explicit scope boundaries — a fence against scope creep during implementation.

- Unchanged feature A.
- Unchanged feature B.

## Semantics

Behavioral rules, edge cases, ordering, and timing. Use tables for testable
conditions:

| Condition | Result |
|-----------|--------|
| X happens | Y occurs |
| X doesn't happen | Z occurs |

Cover: ordering within a tick, interaction with existing features, boundary
cases. State the invariants the design relies on and the invariants it
introduces.

Describe behavior in prose and tables. Do NOT include implementation code blocks
(for-loops, if-statements, function bodies). Wrong: showing a code block of the
loop to insert into `processor.py`. Right: "Mutations apply once per behavior
firing, after decisions are produced. No decisions = no mutation."

## Configuration

YAML examples showing educator-facing config (skip if feature has no config
surface).

```yaml
# Example config
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| field_name | type | Yes/No | What it controls |

## Interface Contracts

Full function signatures with docstrings. Group by category. Signatures and
docstrings ONLY — no implementation bodies, no inline code showing where to
insert changes.

### Config Models

```python
class NewModel(StrictBaseModel):
    """One-line summary."""
    field: Type
```

### Runtime Types

```python
@dataclass
class RuntimeType:
    """One-line summary."""
    field: Type
```

### Functions

```python
def function_name(
    param1: Type1,
    param2: Type2,
) -> ReturnType:
    """
    One-line summary.

    Args:
        param1: Description.
        param2: Description.

    Returns:
        Description.

    Raises:
        ValueError: When X.
    """
```

## Validation Rules

### Parse-Time (Pydantic)

Model validators, field constraints, cross-field checks.

```python
@model_validator(mode='after')
def check_something(self) -> Self:
    """Validates X."""
```

### Business Rules

Rule subclasses registered in the validation runner.

| Rule | Checks | Error Message |
|------|--------|---------------|
| `RuleName` | What it validates | `"Error text with {interpolation}"` |
