# Canonical architecture doc — section spine

The skeleton a folded doc targets. It is the de-facto structure of the
package architecture docs already in the tree (`mechanical.md`,
`seed-tree.md`, the `value-types` docs, `run-driver.md`). A folded doc
matches *this* spine, not the pending doc's narrative arc.

Sections marked **[optional]** are included only when they carry content.
A short doc is fine — `value-types`' docs are 60–120 lines. A doc thin on
*why* is not.

Before writing, open a sibling canonical doc in the destination package
and match its exact section vocabulary; this skeleton is the fallback for
a brand-new package with no sibling.

---

```
# <Subsystem name>

<One-paragraph Purpose: what the subsystem is, where it sits in the
pipeline, what contract it owns. This is where a pending doc's Problem and
Solution land — compressed, stated as fact, not pitched. No "this doc
fixes…", no sprint framing.>

**Source:** <src dir>, <tests dir>. Public API: <__init__.py or entry>.

## Boundary
Inputs, outputs, and forbidden imports / non-inputs. The I/O contract of
the subsystem — what crosses its edge.

## Semantics
The contract body. Topic subsections (`### …`) as the subject needs.
Schema and field shapes are links to the model, not restated tables.
Examples are links to tests. A normative or non-obvious algorithm — a
byte layout, an ordering guarantee, a derivation an independent
reimplementation must honor — is kept here, stated as the contract the
code conforms to.

## Invariants
Numbered. What always holds. Each is checkable.

## Validation Rules        [optional]
Only if the subsystem parses author config. What is rejected, and when
(parse time vs. bind time vs. run time).

## Rationale
Why this design over the alternatives. The rejected options and the
reason they were rejected — stated as settled fact ("X is calendar-level,
not per-window, because …"), never as "we rejected …".

## Forward constraints     [optional]
Constraints this subsystem relies on, honors, or introduces for
subsystems not yet designed. A newly-introduced constraint lives here, in
this doc, and names its retirement trigger inline; one honored/relied-on
references the origin doc. A constraint with no subsystem doc to own it
goes to the note vault as a `decision` with `forward: true`.

## Boundaries
The edges of responsibility — what this subsystem deliberately does NOT
own or do, stated as current contract. This is NOT a sprint's "out of
scope" list: every entry is a permanent boundary with a reason, not a
deferred feature.

## Related
Table of linked docs and why each matters.
```

---

## Naming note: `Boundary` vs `Boundaries`

Two distinct sections, deliberately distinct names:

- **`Boundary`** (singular) — the I/O contract: inputs, outputs, forbidden
  imports. What crosses the subsystem's edge.
- **`Boundaries`** (plural) — the scope edges: what the subsystem
  deliberately does not own.

Some existing docs use only one. Do not merge them; do not coin a third
synonym.
