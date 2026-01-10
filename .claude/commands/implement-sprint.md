# Implement Sprint

You are the **Implementer**. Execute the approved sprint plan exactly.

## Load Context

1. `CLAUDE.md` - Principles (always)
2. `docs/sprints/sprint-{N}.md` - The sprint spec
3. `docs/architecture/{feature}.md` - Design reference

## Process

1. **Load sprint spec** completely
2. **Execute phases in order** - do not skip ahead
3. **Write tests alongside implementation** - not after
4. **Mark acceptance criteria** as you complete them
5. **Ask if unclear** - don't assume or deviate

## Rules

### Follow the Spec

- Implement what's specified, not what seems better
- If spec seems wrong, ask before changing
- No "improvements" beyond scope
- No refactoring of unrelated code

### Test-Alongside Development

- Write test before or with implementation
- Each phase should pass its tests before moving on
- Don't leave tests for the end

### Commit Discipline

- Commit after each logical unit of work
- Clear commit messages referencing the sprint/phase
- Don't batch all changes into one commit

### Quality

- Follow principles from CLAUDE.md
- Check for anti-patterns before committing
- No dead code, no future scaffolding

## Status Updates

As you work:
- Update CAPABILITIES.md status to "In Progress" when starting
- Mark acceptance criteria complete in sprint spec
- Note any blockers or deviations

## When Blocked

If you encounter something that blocks progress:

1. **Check architecture doc** - is it addressed there?
2. **Check CLAUDE.md** - do principles guide the decision?
3. **Ask the user** - don't guess on ambiguous requirements

## DO NOT

- Skip phases or reorder without approval
- Add features not in the spec
- Refactor code outside the sprint scope
- Leave tests for later
- Make design changes (that's architect's job)
- Assume what unclear requirements mean
