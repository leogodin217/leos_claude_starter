# Feature Name

**Status:** Design draft

---

## Problem

What's wrong or missing. Include a concrete example: config snippet showing the limitation, error message, or workflow that doesn't work.

## Solution

High-level approach. One paragraph describing the design direction, plus a diagram or YAML snippet showing the end state.

---

## Semantics

Behavioral rules, edge cases, ordering, and timing. Use tables for testable conditions:

| Condition | Result |
|-----------|--------|
| X happens | Y occurs |
| X doesn't happen | Z occurs |

Cover: ordering within a tick, interaction with existing features, boundary cases.

Describe behavior in prose and tables. Do NOT include implementation code blocks (for-loops, if-statements, function bodies). Wrong: showing a code block of the loop to insert into `processor.py`. Right: "Mutations apply once per behavior firing, after decisions are produced. No decisions = no mutation."

## Configuration

YAML examples showing educator-facing config (skip if feature has no config surface).

```yaml
# Example config
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| field_name | type | Yes/No | What it controls |

## Interface Contracts

Full function signatures with docstrings. Group by category. Signatures and docstrings ONLY — no implementation bodies, no inline code showing where to insert changes.

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

For modified functions, describe the behavioral change in the docstring. Do not show the implementation diff — that's the sprint implementer's job.

## Implementation Impact

### Source Files

| Action | File | Change |
|--------|------|--------|
| Create | `packages/.../new_module.py` | New module for X |
| Modify | `packages/.../existing.py` | Add Y field, update Z |

### Test Files

| Action | File | Change |
|--------|------|--------|
| Create | `packages/.../tests/test_new.py` | Unit tests for X |
| Modify | `packages/.../tests/test_existing.py` | Add cases for new behavior |

### Import Updates

Files affected by moved, renamed, or relocated symbols.

| File | Current Import | New Import |
|------|---------------|------------|
| `path/to/file.py` | `from old.module import X` | `from new.module import X` |

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

## What Doesn't Change

Explicit scope boundaries. List things that stay the same to prevent scope creep during implementation.

- Unchanged feature A (stays as-is because...)
- Unchanged feature B (not affected because...)

---

*Ready for sprint planning.*
