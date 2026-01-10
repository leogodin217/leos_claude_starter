# {Subsystem Name}

{One-line description of what this subsystem does.}

---

## Overview

{2-3 paragraphs explaining:
- What problem this subsystem solves
- Key concepts and terminology
- How it fits into the larger system}

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| {Term} | {Definition} |
| {Term} | {Definition} |

---

## Design Decisions

### {Decision 1: e.g., "Chose X over Y"}

**Context:** {What problem were we solving? What constraints existed?}

**Decision:** {What we chose to do}

**Rationale:** {Why this approach over alternatives}

**Constraints:** {What this decision rules out or limits}

### {Decision 2}

**Context:** {Description}

**Decision:** {Description}

**Rationale:** {Description}

**Constraints:** {Description}

---

## Invariants

Properties that must always hold for this subsystem:

| Invariant | Meaning |
|-----------|---------|
| {Name} | {What must always be true} |
| {Name} | {What must always be true} |

---

## Interfaces

<!-- Before implementation: sketch key interfaces -->
<!-- After implementation: link to code -->

**Key functions/classes:**

```python
# Example interface sketch (remove after implementation)
def process_item(
    item: ItemType,
    config: ConfigType,
) -> ResultType:
    """
    One-line summary.

    Args:
        item: Description
        config: Description

    Returns:
        Description

    Raises:
        ValueError: When X
    """
    ...
```

**Location:** `src/{path}/`

---

## Configuration

<!-- If this subsystem has configuration, describe the schema -->

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| {field} | {type} | Yes/No | {description} |

---

## Error Handling

| Error Condition | Behavior |
|-----------------|----------|
| {Condition} | {What happens - error type, message pattern} |
| {Condition} | {What happens} |

---

## Related Documents

| Document | Relationship |
|----------|--------------|
| [{name}.md]({name}.md) | {How they relate - depends on, extends, etc.} |
| [CLAUDE.md](../../CLAUDE.md) | Principles governing this design |

---

## Implementation Notes

<!-- Add after implementation, delete before -->

**Status:** Not Started / In Progress / Complete

**Key files:**
- `src/{path}/{file}.py` - {description}

---

*Design rationale. See code for implementation details.*
