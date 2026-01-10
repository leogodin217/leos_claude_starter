# Sprint: {Sprint Name}

## Goal

{One sentence: what does this sprint deliver? What will be true when it's done?}

## Architecture Reference

[{feature}.md](../architecture/{feature}.md)

---

## Phases

### Phase 1: {Phase Name}

**Delivers:** {Concrete, testable deliverable}

**Files:**
- `src/{path}/{file}.py` - {what it does}
- `tests/{path}/test_{file}.py` - {what it tests}

**Implementation notes:**
- {Key implementation detail}
- {Another detail}

**Acceptance criteria:**
- [ ] {Specific, verifiable criterion}
- [ ] {Another criterion}
- [ ] Tests pass

---

### Phase 2: {Phase Name}

**Delivers:** {Concrete deliverable}

**Files:**
- {files}

**Dependencies:** Phase 1 must be complete

**Implementation notes:**
- {details}

**Acceptance criteria:**
- [ ] {criterion}
- [ ] Tests pass

---

### Phase 3: {Phase Name}

**Delivers:** {Concrete deliverable}

**Files:**
- {files}

**Dependencies:** Phases 1-2 must be complete

**Acceptance criteria:**
- [ ] {criterion}
- [ ] Tests pass
- [ ] Integration tests pass

---

## Out of Scope

Explicitly excluded from this sprint:
- {Thing that might seem in scope but isn't}
- {Another exclusion}

---

## Test Strategy

| Type | Scope | Location |
|------|-------|----------|
| Unit | {what's unit tested} | `tests/unit/` |
| Integration | {what's integration tested} | `tests/integration/` |

---

## Risks

| Risk | Mitigation |
|------|------------|
| {Potential issue} | {How we'll handle it} |

---

## Definition of Done

- [ ] All phases complete
- [ ] All tests pass
- [ ] Code reviewed (/review-sprint)
- [ ] Docs updated (CAPABILITIES.md status, architecture doc pruned)
- [ ] No principle violations
