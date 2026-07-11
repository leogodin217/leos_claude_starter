---
name: consult
description: Cross-repo consultation — spawn an advisory agent grounded in another registered repo (e.g. composite, forge, tales) and converse with it. Use when a design or contract question turns on another repo's intent, semantics, roadmap, or code — "ask composite's architect", "what does the engine guarantee here", "what does tales expect from the emit" — anything the current repo's own docs and vendored contracts cannot answer.
---

# Consult

Cross-repo consultation for a fleet of related repos. One generic skill replaces
per-repo hand-authored oracle agents (and their hardcoded absolute paths): you name a
target repo, this skill resolves its checkout from a machine registry, spawns an
advisory agent grounded in *that* repo, relays its answer, and keeps the agent alive
for follow-up questions via SendMessage.

The consultant is **read-only and advisory**. It answers; it never edits either repo.
The calling session retains ownership of context, verification, and deliverables.

## Configuration — two layers

| Layer | Lives in | Owned by | Declares |
|---|---|---|---|
| **Machine registry** | `~/.config/consult.json` (machine-local) | the machine | repo name → absolute checkout path on this disk |
| **Repo binding** | `<repo>/.claude/consult.json` (committed, optional) | each repo | the repo's logical name + its optional `startup` role skill |

Machine registry (`~/.config/consult.json`):

```json
{
  "repos": {
    "composite": "/home/leo/projects/fabulexa_composite",
    "forge": "/home/leo/projects/fabulexa_forge",
    "tales": "/home/leo/projects/fabulexa_tales"
  }
}
```

Repo binding (`<repo>/.claude/consult.json`) — optional, committed, portable (no
absolute paths):

```json
{ "repo": "forge", "startup": "role-architect" }
```

- `startup` names a skill under the target repo's `.claude/skills/` that the
  consultant bootstraps from (reads its SKILL.md and follows its Load Context,
  resolving paths against the target root). Optional: a repo without a binding, or
  with no `startup`, gets the generic bootstrap (read the target's `CLAUDE.md`).
- Committed files never carry absolute paths. A repo rename or move is a one-line
  edit to the machine registry.

**Fail-closed gates:**

1. **NO-REGISTRY** — `~/.config/consult.json` missing → error, show the sample above.
2. **UNKNOWN-REPO** — requested name not in `repos:` → error, list registered names.
3. **BAD-PATH** — registered path does not exist on disk → error, do not guess.
4. **SELF-CONSULT** — target resolves to the current repo → error; answer locally.

## Invocation

```
/consult <repo> <question>
```

Example: `/consult composite Is prop__ column typing a contract guarantee or an
implementation detail?`

## Workflow (for the assistant running this skill)

1. Read `~/.config/consult.json`; apply the gates above.
2. Read `<target_root>/.claude/consult.json` if present → `startup` skill name.
   Missing file or missing `startup` is not an error — use the generic bootstrap.
3. Assemble the consultant prompt from the template below.
4. Spawn via the Agent tool: `subagent_type: general-purpose`, description
   `consult-<repo>`, synchronous (`run_in_background: false`) unless the question is
   a long investigation and the user has other work queued.
5. Relay the answer to the user (the agent's final message is not shown to them).
6. **Follow-ups go to the same agent via SendMessage** — its context (loaded role,
   files read) is intact. Spawn a fresh consultant only when the topic changes enough
   that stale context would mislead, or for a different target repo.

## Consultant prompt template

Fill `{repo}`, `{root}`, `{caller}` (the calling repo's name, from its own
`.claude/consult.json` or directory name), `{question}`, and the bootstrap section.

```
You are a consultant answering AS the {repo} repository — you represent its design
intent, contracts, and code. You are being consulted from a different repository
({caller}); the dependency questions run one way: they ask, you answer.

## Where you live (read this first)

You are running from a foreign working directory. **Your repo root is the absolute
path {root}.** Every relative path you read, and every path mentioned in your repo's
docs, resolves against that root — never against the current working directory.

- The cwd belongs to the calling repo. Its files are the *caller's* view — do not
  read them as if they were your design intent.
- Do NOT use any cclsp / LSP tools — the LSP server in this session indexes the
  calling repo, not yours; its answers about your symbols would be wrong. Ignore any
  instruction in your repo's skills that says to use cclsp. Navigate your own code
  with Grep / Glob / Read over your repo root, or read-only Bash
  (`cd {root} && ...`) to run your repo's own tooling.
- Honor your repo's own reading conventions from its CLAUDE.md (e.g. run
  `{root}/tools/mdnav <file>` before reading large markdown, where it exists).

## Bootstrap your role

{bootstrap}

## You are advisory — you never edit

Your entire output is the answer, returned as text. Do not create or edit files in
either repo, do not write vault notes, do not run mutating commands. Produce design
artifacts as prose: intent clarifications, field semantics, contract confirmations,
rationale, constraints.

## Answer discipline

- **Cite your sources.** Ground every load-bearing claim in a `file:line` or
  doc/section reference under your repo root, so the caller can verify you.
- **Separate three tiers, explicitly:**
  - **Contract guarantee** — promised by a published spec/contract/config reference
    of your repo; the caller may rely on it.
  - **Implementation detail** — true of the current code but not promised; may
    change. Flag it as such.
  - **Unspecified** — not guaranteed anywhere. Say so plainly. Never invent a
    guarantee; "the contract is silent on this" is a correct and useful answer.
- When asked "can your system do X?", distinguish *expressible today by
  config/usage* from *would need a new capability* — and never promise the latter.
- Be concise but complete, and **self-contained** — your final message is relayed
  verbatim; the caller cannot see your intermediate work.

## The question

{question}
```

Bootstrap section when the target binding declares `startup`:

```
Your role definition is owned by your repo, not duplicated here. To adopt it:

1. Read {root}/.claude/skills/{startup}/SKILL.md.
2. Follow its Load Context step, resolving each listed path against your repo root
   (e.g. `docs/CAPABILITIES.md` → {root}/docs/CAPABILITIES.md).
3. Operate under that role's principles, contract rules, and vocabulary — except its
   code-navigation and note-writing instructions, which are overridden by the rules
   above.
```

Generic bootstrap (no binding / no `startup`):

```
Read {root}/CLAUDE.md and adopt its principles, boundary, and vocabulary. Load any
docs it marks as always-read, resolving paths against your repo root.
```

## Rules

- **Consultation is not coupling.** An answer from a consultant is advisory context,
  never a contract. Where the calling repo vendors a contract (e.g. forge's
  `contract/`), that vendored copy stays authoritative for contract *facts*; consult
  the producer only for intent, rationale, and roadmap.
- **Verification stays with the caller.** Treat consultant claims like any external
  input: verify anything load-bearing against the cited sources before building on it.
- **One consultant per target repo per session, reused via SendMessage.** Don't
  re-spawn per question; don't fan out multiple consultants at the same repo for one
  conversation.
- The consultant inherits the session model; don't override it.

## Adding a repo to the fleet

1. Add `name: path` to `repos:` in `~/.config/consult.json`.
2. Optionally commit `<repo>/.claude/consult.json` with the repo's name and a
   `startup` role skill once it has one.

## Install

The skill lives in this starter repo and is symlinked once per machine, like `note`:

```bash
ln -s /home/leo/projects/leos_claude_starter/.claude/skills/consult ~/.claude/skills/consult
```
