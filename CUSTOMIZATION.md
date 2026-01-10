# Customization Guide

How to adapt this template for your specific project.

---

## Step 1: Define Your Principles

Principles are the most important customization. They guide all decisions.

### Characteristics of Good Principles

| Good | Bad |
|------|-----|
| Specific and actionable | Vague and aspirational |
| Include examples | Abstract only |
| Sometimes conflict | Always harmonious |
| Say what NOT to do | Only positive statements |

### Principle Categories

Consider one principle from each category:

1. **User Focus** - What must be true about user experience?
   - "Users succeed without code"
   - "Power users can customize everything"
   - "Sensible defaults, full control available"

2. **Configuration Philosophy** - How flexible vs. opinionated?
   - "All behavior is configurable"
   - "Convention over configuration"
   - "Minimal configuration, smart defaults"

3. **Quality Philosophy** - What tradeoffs are acceptable?
   - "Good enough beats perfect"
   - "Correctness is non-negotiable"
   - "Fast iteration over careful planning"

4. **Error Handling** - How to handle problems?
   - "Fail fast with clear errors"
   - "Be lenient and recover gracefully"
   - "Degrade gracefully, never crash"

5. **Change Policy** - How stable is the interface?
   - "Breaking changes are acceptable" (greenfield)
   - "Backward compatibility required" (mature)
   - "Semver strictly enforced"

### How Many Principles?

- **Minimum:** 5 (fewer = gaps in guidance)
- **Maximum:** 9 (more = can't remember them)
- **Sweet spot:** 6-7

### Writing Principle Examples

Each principle should have:

```markdown
### {Principle Name}

{One sentence explanation}

**What this means:**
- {Concrete behavior}
- {Another behavior}

**What this prohibits:**
- {Specific anti-pattern}
- {Another anti-pattern}

**Example:**
{Code or config showing principle in action}
```

---

## Step 2: Define Your Invariants

Invariants are properties that must ALWAYS hold. They're stricter than principles.

### Good Invariants

| Invariant | Why It's Good |
|-----------|---------------|
| "Timestamps never decrease" | Testable, always true |
| "All IDs are unique" | Testable, always true |
| "Config errors fail before processing" | Clear timing guarantee |

### Bad Invariants

| Invariant | Why It's Bad |
|-----------|--------------|
| "Code is clean" | Subjective |
| "Errors are handled" | Vague |
| "Performance is good" | Not measurable as invariant |

### How to Find Invariants

Ask:
- What would break everything if violated?
- What do all tests assume is true?
- What would users rely on being always true?

---

## Step 3: Define Anti-Patterns

Anti-patterns are concrete mistakes to avoid. Add them as you discover them.

### Starting Anti-Patterns

The template includes universal anti-patterns:
- Over-engineering patterns
- Dead code patterns
- Test anti-patterns

### Adding Domain-Specific Anti-Patterns

When you catch a mistake during review, ask:
- Is this likely to recur?
- Can I describe it concretely?
- Is the fix clear?

If yes to all three, add it to CLAUDE.md:

```markdown
### {Domain} Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|--------------|-----|
| {Specific pattern} | {Consequence} | {Solution} |
```

---

## Step 4: Structure Your Capabilities

CAPABILITIES.md tracks what the system does.

### Capability Granularity

- **Too coarse:** "Backend" - not useful
- **Too fine:** "Parse JSON field X" - too detailed
- **Right level:** "User Authentication", "Data Export", "Search"

Each capability should be:
- Independently understandable
- Worth tracking status for
- Large enough to need architecture doc

### Status Values

| Status | Meaning |
|--------|---------|
| Not Started | May have architecture doc, no code |
| In Progress | Active sprint implementing |
| Complete | Implemented, tested, documented |

---

## Step 5: Create Architecture Docs

Create one architecture doc per major subsystem.

### When to Create

Create an architecture doc when:
- Feature is non-trivial (multiple components)
- Design decisions need rationale
- Multiple people will work on it
- Implementation isn't obvious

### What to Include

**Before implementation:**
- Overview and key concepts
- Design decisions with rationale
- Invariants
- Interface sketches

**After implementation (prune):**
- Keep: rationale, constraints, invariants
- Remove: details now in code
- Add: links to implementation

---

## Step 6: Customize Commands

The template includes five commands. Customize as needed.

### Modifying Commands

Each command in `.claude/commands/` can be customized:

- **Add domain context** - Reference your specific docs
- **Add checklists** - Domain-specific review items
- **Add rules** - Domain-specific constraints

### Adding New Commands

Create new `.md` files in `.claude/commands/`:

```markdown
# {Command Name}

You are the **{Role}**. {One sentence purpose.}

## Load Context
{What to read}

## Process
{Steps to follow}

## Rules
{Constraints}

## DO NOT
{Explicit prohibitions}
```

### Example: Domain-Specific Reviewer

```markdown
# Security Review

You are the **Security Reviewer**.

## Load Context
1. CLAUDE.md
2. Security architecture doc
3. Code changes

## Checklist
- [ ] No SQL injection
- [ ] No XSS vulnerabilities
- [ ] Auth checks on all endpoints
- [ ] Secrets not in code
...
```

---

## Step 7: Customize Agents

The template includes two starter agents in `.claude/agents/`:

| Agent | Purpose |
|-------|---------|
| `architect` | System design, contracts, architecture docs |
| `implementer` | Code, tests, matching specs exactly |

### Agent File Format

Agents are markdown files with YAML frontmatter:

```markdown
---
name: agent-name
description: Brief description for Task tool
tools: Read, Grep, Glob, Write, Edit
model: sonnet
---

You are the {Role} for this project.

## Your Purpose
{What this agent does}

## What You Produce
{Outputs}

## What You Do NOT Do
{Explicit constraints}
```

### Adding Domain-Specific Agents

Common agents to add as your project grows:

| Agent | When to Add |
|-------|-------------|
| `reviewer` | When you want fresh-eyes code review |
| `data-analyst` | When you need to validate output data |
| `doc-auditor` | When documentation accuracy matters |
| `test-reviewer` | When test quality is important |
| `security-reviewer` | When security review is needed |

### Agent Design Principles

1. **Minimal context** - Load only what's needed
2. **Clear constraints** - Explicit "do not" section
3. **Specific outputs** - Define exactly what the agent produces
4. **Tool restrictions** - Only grant tools the agent needs

### Example: Adding a Reviewer Agent

Create `.claude/agents/reviewer.md`:

```markdown
---
name: reviewer
description: Fresh-eyes code reviewer. Loads minimal context intentionally.
tools: Read, Grep, Bash
model: sonnet
---

You are the Reviewer. You review code with fresh eyes.

## Fresh Eyes Protocol

You intentionally load MINIMAL context:
- The sprint spec (current phase only)
- The principles from CLAUDE.md
- The implementation diff

## What You Check

- [ ] Code matches spec
- [ ] No principle violations
- [ ] No anti-patterns from CLAUDE.md

## Output

APPROVED or REVISIONS NEEDED with specific issues.

## What You Do NOT Do

- Fix code yourself
- Make architectural suggestions
- Approve code with principle violations
```

---

## Step 8: Use the SCRATCHPAD

`docs/SCRATCHPAD.md` tracks current work across sessions.

### When to Use

Reset the SCRATCHPAD for each major effort:
- New feature implementation
- QA cycle
- Major refactoring
- Migration

### What to Track

| Section | Purpose |
|---------|---------|
| Goal | What we're trying to accomplish |
| Exit Criteria | When this work is done |
| Decisions | Choices made with rationale |
| Phases | Work breakdown with status |
| Context Management | Notes for agent invocations |

### SCRATCHPAD vs Sprint Specs

| SCRATCHPAD | Sprint Spec |
|------------|-------------|
| Working document | Formal specification |
| Updated frequently | Written once, tracked |
| Decisions and notes | Phases and acceptance criteria |
| One per major effort | One per sprint |

Use SCRATCHPAD for informal tracking alongside formal sprint specs.

---

## Maintenance

### Weekly

- Update CAPABILITIES.md status
- Run `/audit-docs` on completed features

### After Each Sprint

- Prune architecture docs
- Add discovered anti-patterns
- Update invariants if needed

### Quarterly

- Review principles - still relevant?
- Clean up unused commands
- Archive old sprint specs

---

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Too many principles | Can't remember them | Consolidate to 5-9 |
| Vague principles | No guidance | Add concrete examples |
| No anti-patterns | Same mistakes repeat | Add as discovered |
| Stale docs | Misleading | Regular audits |
| Skipping architecture | Implementation drift | Require arch doc before sprint |
