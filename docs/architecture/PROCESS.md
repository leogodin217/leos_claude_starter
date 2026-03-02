# Development Process

How we architect, develop, and document this project.

---

## Design Timing

**Last responsible moment:** Design when you have enough context to decide well—not before, not after.

This is about information, not calendars. Design a subsystem when:
- You understand the problem it solves
- You know the constraints it operates under
- Delaying further would force rework

---

## What Gets Designed When

| Category | When to Design | Examples |
|----------|----------------|----------|
| **Foundational** | Before any implementation touches it | Core data model, processing loop, key invariants |
| **Structural** | Before implementing the subsystem | Feature architecture, API contracts, data schemas |
| **Emergent** | During implementation | Specific algorithms, optimizations, edge case handling |

Foundational designs can (and should) exist before sprints that implement them. The design captures the vision; sprints implement pieces of it.

---

## Sprints vs Design

**Sprints** define implementation scope—what gets built now.

**Architecture docs** capture system design—how subsystems work.

These are independent:
- A sprint may implement part of an existing design
- A sprint may require new design work
- Design docs may describe things not yet implemented

---

## Code Is Truth

Once implemented, code is the specification.

| Before Implementation | After Implementation |
|-----------------------|----------------------|
| Doc specifies behavior | Code specifies behavior |
| Doc defines interfaces | Code defines interfaces |
| Doc has examples | Tests have examples |

Docs link to code, not duplicate it.

---

## What Lives Where

| Content | Location |
|---------|----------|
| Principles, invariants | `CLAUDE.md` |
| System capabilities | `docs/CAPABILITIES.md` |
| System design | `docs/architecture/*.md` |
| Sprint scope | `docs/sprints/sprint-N.md` |
| Algorithms | Code + docstrings |
| Examples | Tests |

---

## Documentation Lifecycle

### Write (Before/During Implementation)

- Interfaces and contracts
- Non-obvious decisions and rationale
- Constraints (what we ruled out)
- Invariants (what must always hold)

### Prune (After Implementation)

- Schema details → link to schema files or code
- Algorithm steps → link to code
- Examples → link to tests
- Delete anything code makes obvious

### Keep (Always)

- Rationale (why X over Y)
- Constraints (what's explicitly not supported)
- Invariants (rules that must hold)

---

## Feature Lifecycle

```
1. NEED IDENTIFIED
   └── User request, bug, or roadmap item

2. ARCHITECTURE (/arch-design)
   ├── Create docs/architecture/{feature}.md
   │   ├── Design decisions with rationale
   │   ├── Invariants
   │   └── Interface sketches
   └── Update docs/CAPABILITIES.md
       ├── Add capability section
       └── Status: "Not Started"

3. SPRINT PLANNING (/create-sprint)
   ├── Reference architecture doc
   ├── Break into phases
   └── Create docs/sprints/sprint-N.md

4. SPRINT EVALUATION (/eval-sprint)
   └── Review spec for completeness before implementation

5. IMPLEMENTATION (/implement-sprint)
   ├── Execute phases in order
   ├── Write tests alongside code
   └── Update CAPABILITIES.md status → "In Progress"

6. REVIEW (/review-sprint)
   ├── Verify against sprint spec
   ├── Check principle compliance
   └── Verify test coverage

7. VERIFICATION (/verify-sprint)
   └── Final verification of sprint deliverables

8. DOCUMENTATION (/audit-docs)
   ├── Prune architecture doc (link to code)
   ├── Update CAPABILITIES.md status → "Complete"
   └── Verify docs match implementation
```

---

## Anti-Patterns

| Don't | Why |
|-------|-----|
| Duplicate schema in prose | Drifts from code |
| Write examples in docs | Tests are better examples |
| Keep stale documentation | Misleads future readers |
| Design without understanding | Premature abstraction |
| Delay design until sprint needs it | Fragments coherent subsystems |
