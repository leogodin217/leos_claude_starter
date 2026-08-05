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
    "composite": {
      "path": "/home/leo/projects/fabulexa_composite",
      "does": "The simulation engine (aka 'the engine'). Runs scenario YAML into a deterministic base-layer emit. Pure producer."
    },
    "forge": {
      "path": "/home/leo/projects/fabulexa_forge",
      "does": "Downstream exporter + corrupter (aka 'export'). Reads a base-layer emit, writes datasets or realistically-broken bases."
    }
  },
  "interfaces": [
    "base-layer emit: run.duckdb + base.json @ base_format_version 4 — produced by composite, consumed by forge and tales."
  ]
}
```

- A repo entry is either the object form above (`path` required; `does` is an
  optional one-to-two-sentence helper: what the repo is, common aliases, its side of
  the shared contracts) or, back-compat, a bare path string.
- Top-level `interfaces` (optional) lists the fleet's shared contracts — who
  produces, who consumes, where the spec lives. Fleet-level facts only; per-repo
  detail belongs in `does`.
- The helper text serves two things: resolving loose requests to a repo, and giving
  the consultant a fleet map. Keep it a sketch — the consultant bootstraps its real
  role from the target repo itself, so drift here is cheap but not free.

Repo binding (`<repo>/.claude/consult.json`) — optional, committed, portable (no
absolute paths):

```json
{ "repo": "composite", "startup": "understand", "startup_args": "architecture" }
```

- `startup` names a skill under the target repo's `.claude/skills/` that the
  consultant bootstraps from (reads its SKILL.md and follows its Load Context,
  resolving paths against the target root). Optional: a repo without a binding, or
  with no `startup`, gets the generic bootstrap (read the target's `CLAUDE.md`).
- `startup_args` (optional) is the argument string the startup skill would receive
  if a user invoked it — e.g. which `understand` context bundle to load. It fills
  `{startup_args}` in the bootstrap template; absent means empty.
- Committed files never carry absolute paths. A repo rename or move is a one-line
  edit to the machine registry.

**Name resolution.** An exact `repos:` key wins. Otherwise match the request against
the `does` helpers (aliases, roles — "export" → forge, "the engine" → composite).
A single confident match resolves — say which repo you resolved to and why. No match,
or two plausible matches → UNKNOWN-REPO / ask, don't guess.

**Fail-closed gates:**

1. **NO-REGISTRY** — `~/.config/consult.json` missing → error, show the sample above.
2. **UNKNOWN-REPO** — request resolves to no registered repo → error, list registered
   names with their `does` lines.
3. **BAD-PATH** — registered path does not exist on disk → error, do not guess.
4. **SELF-CONSULT** — target resolves to the current repo → error; answer locally.

## Invocation

```
/consult <repo> <question>
```

Example: `/consult composite Is prop__ column typing a contract guarantee or an
implementation detail?`

## Workflow (for the assistant running this skill)

1. Read `~/.config/consult.json`; resolve the name and apply the gates above.
2. Read `<target_root>/.claude/consult.json` if present → `startup` skill name and
   optional `startup_args`. Missing file or missing `startup` is not an error — use
   the generic bootstrap.
3. Assemble the consultant prompt from the template below. `{fleet}` = the registry's
   `does` line per repo plus the `interfaces` list, rendered as bullets; if the
   registry has neither, drop the fleet section entirely.
4. Spawn via the Agent tool: `subagent_type: general-purpose`, description
   `consult-<repo>`, synchronous (`run_in_background: false`) unless the question is
   a long investigation and the user has other work queued.
5. Relay the answer to the user (the agent's final message is not shown to them).
6. **Follow-ups go to the same agent via SendMessage** — its context (loaded role,
   files read) is intact. Spawn a fresh consultant only when the topic changes enough
   that stale context would mislead, or for a different target repo.

## The panel pattern (one proposal, several affected repos)

For a change in *this* repo that affects several others — typically a producer
sounding out its consumers before touching a shared contract — run one consultant
per affected repo as a panel:

1. **Round 1, parallel.** Spawn all consultants concurrently (one Agent message,
   multiple tool calls), same proposal to each. The proposal travels **in the
   question** — paste the sketch/diff or name concrete paths; each consultant judges
   it against its own repo's *current* state, which is the right baseline for
   "would this break you."
2. **Round 2+, cross-examination.** Consultants never address each other; the
   calling session mediates. SendMessage each one the others' conflicting asks and
   relay what moves. Converge in a round or two — a panel that keeps disagreeing is
   surfacing a real design tension, not a consultation failure; bring that to the
   user rather than forcing consensus.
3. **Decide with the caller.** Panel answers are advisory input to a decision the
   calling repo (and the user) owns. Record the decision on the caller's side; if it
   changes a shared contract, each consumer's vendored copy updates through that
   repo's own process, never by the panel.

Note the direction flip: the template's framing ("they ask, you answer") is about
the *consultation*, not the dependency. A producer consulting its consumers is the
same mechanism with the fleet map providing orientation.

## Consultant prompt template

Fill `{repo}`, `{root}`, `{caller}` (the calling repo's name, from its own
`.claude/consult.json` or directory name), `{question}`, and the bootstrap section.

```
You are a consultant answering AS the {repo} repository — you represent its design
intent, contracts, and code. You are being consulted from a different repository
({caller}); the dependency questions run one way: they ask, you answer.

## The fleet (orientation, not authority)

The repos on this machine and the contracts between them, as the caller's registry
sketches them:

{fleet}

This is orientation only — where the caller sits relative to you and which shared
contract the question probably rides on. Your own repo's docs are authoritative over
this sketch wherever they disagree.

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

1. Read {root}/.claude/skills/{startup}/SKILL.md. Your invocation arguments are:
   `{startup_args}` (may be empty).
2. Follow its Load Context step, resolving each listed path against your repo root
   (e.g. `docs/CAPABILITIES.md` → {root}/docs/CAPABILITIES.md). If the skill is a
   command-substitution skill (its body is a `!`-prefixed command), run that
   command yourself with paths resolved against your repo root and the invocation
   arguments above in place of `$ARGUMENTS` (e.g.
   `{root}/.claude/skills/{startup}/load.py {root} {startup_args}`).
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

1. Add the repo to `repos:` in `~/.config/consult.json` — object form with `path` +
   a one-line `does` (include common aliases). Touch up `interfaces` if it changes
   the fleet's contract picture.
2. Optionally commit `<repo>/.claude/consult.json` with the repo's name and a
   `startup` role skill once it has one.

## Install

The skill lives in this starter repo and is symlinked once per machine, like `note`:

```bash
ln -s /home/leo/projects/leos_claude_starter/.claude/skills/consult ~/.claude/skills/consult
```
