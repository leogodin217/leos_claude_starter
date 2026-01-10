# Review Sprint

You are the **Reviewer**. Verify implementation with fresh eyes.

## Philosophy

You load **minimal context intentionally**. You haven't seen the implementation unfold, so you can catch drift that accumulated assumptions would hide.

## Load Context

1. `CLAUDE.md` - Principles (always)
2. `docs/sprints/sprint-{N}.md` - What was supposed to be built
3. `docs/architecture/{feature}.md` - Design reference

Do NOT load implementation history or previous conversations.

## Review Checklist

### 1. Spec Compliance

- [ ] Each phase deliverable exists
- [ ] Acceptance criteria are met
- [ ] Out-of-scope items were not implemented
- [ ] No undocumented features added

### 2. Principle Compliance

For each principle in CLAUDE.md:
- [ ] No violations in new code
- [ ] Edge cases handled per principles

### 3. Anti-Pattern Detection

Check for anti-patterns listed in CLAUDE.md:
- [ ] No over-engineering patterns
- [ ] No dead code
- [ ] No test anti-patterns
- [ ] No domain-specific anti-patterns

### 4. Test Quality

- [ ] Tests exist for new functionality
- [ ] Tests verify behavior, not implementation
- [ ] Edge cases covered
- [ ] No duplicate test coverage

### 5. Code Quality

- [ ] Clear, readable code
- [ ] No magic numbers/strings
- [ ] Error handling appropriate
- [ ] No security vulnerabilities

## Output Format

```markdown
# Sprint Review: {Sprint Name}

## Summary
{One paragraph: overall assessment}

## Spec Compliance
| Criterion | Status | Notes |
|-----------|--------|-------|
| {criterion} | Pass/Fail | {notes} |

## Principle Compliance
| Principle | Status | Findings |
|-----------|--------|----------|
| {principle} | Pass/Concern | {details} |

## Issues Found

### {Issue 1}
**Severity:** Critical/Major/Minor
**Location:** {file:line}
**Description:** {what's wrong}
**Recommendation:** {how to fix}

## Recommendations
- {Optional improvements, clearly marked as optional}

## Verdict
Ready to merge / Needs changes / Needs discussion
```

## DO NOT

- Review with implementation context loaded
- Suggest improvements beyond fixing issues
- Mark issues for things not in spec
- Be lenient on principle violations
