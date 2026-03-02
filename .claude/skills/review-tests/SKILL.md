---
name: review-tests
description: Comprehensive test review using parallel test-reviewer agents.
disable-model-invocation: true
---

# Review Tests

Orchestrate a comprehensive test review using parallel test-reviewer agents.

## Process

### 1. Discover

Find all test files:
```
Glob: **/test_*.py, **/*_test.py
```

Map each test file to its source:
- `tests/test_foo.py` → `src/.../foo.py`
- `src/.../tests/test_bar.py` → `src/.../bar.py`

Report: "Found N test files covering M source modules"

### 2. Plan Parallelization

Group tests for parallel review. Options:
- By file (maximum parallelism)
- By module (balanced)
- By package (fewer agents)

Default: By module (all tests for a source module → one agent)

### 3. Launch Agents

For each group, launch test-reviewer agent:
```
Task(
    subagent_type="test-reviewer",
    prompt="Review tests.\n\ntest_path: {paths}\nsource_path: {paths}",
    run_in_background=true
)
```

Launch ALL agents in a single message for true parallelism.

### 4. Collect Results

Wait for all agents to complete. Gather structured output.

### 5. Aggregate

Combine findings across all agents:

```markdown
# Test Review Summary

## Overall
- Files reviewed: N
- Tests reviewed: N
- Remove: N | Improve: N | Add: N | Keep: N

## By Priority

### High (Remove - tests with no value)
[List across all files]

### Medium (Add - important gaps)
[List across all files]

### Low (Improve - existing tests to refine)
[List across all files]

## By Module
[Findings grouped by source module]
```

### 6. Recommendations

Based on findings, recommend:
1. Tests to delete immediately
2. Critical gaps to fill
3. Improvements to make
4. Whether overall test health is good/fair/poor
