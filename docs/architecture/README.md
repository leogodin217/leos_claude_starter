# Architecture

{One-line description of the system.}

---

## Data Flow

```
{ASCII diagram showing how data flows through the system}

Example:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Input     │───▶│  Validate   │───▶│   Process   │───▶│   Output    │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Reading Order

### Always Load First

1. **[CLAUDE.md](../../CLAUDE.md)** - Principles and invariants
2. **This file** - Architecture overview

### By Task

| Working On | Load These |
|------------|------------|
| {Capability 1} | [{doc1}.md]({doc1}.md) → [{doc2}.md]({doc2}.md) |
| {Capability 2} | [{doc3}.md]({doc3}.md) |
| {Capability 3} | [{doc4}.md]({doc4}.md) → [{doc1}.md]({doc1}.md) |

### Independent References

These docs stand alone—load as needed:
- [{doc}.md]({doc}.md) - {One-line description}
- [PROCESS.md](PROCESS.md) - Development process

---

## Core Concepts

| Concept | One-liner | Doc |
|---------|-----------|-----|
| {Concept} | {Brief description} | [{doc}.md]({doc}.md) |
| {Concept} | {Brief description} | [{doc}.md]({doc}.md) |

---

## Invariants

Non-negotiable rules (see [CLAUDE.md](../../CLAUDE.md) for full list):

| Invariant | Meaning |
|-----------|---------|
| {Name} | {Description} |
| {Name} | {Description} |

---

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| {Component} | Not Started / In Progress / Complete | `src/{path}/` |
| {Component} | Not Started / In Progress / Complete | `src/{path}/` |

---

## Document Index

| Topic | Document |
|-------|----------|
| Development process | [PROCESS.md](PROCESS.md) |
| {Topic} | [{doc}.md]({doc}.md) |

---

*This document is the entry point. Details live in linked docs and code.*
