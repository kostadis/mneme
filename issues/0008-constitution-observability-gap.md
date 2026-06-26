# 0008 — constitution gap: observability is not a named principle

**Status:** open (filed 2026-06-26; **deferred** — address after feature 002 lands)
**Area:** constitution · doctrine · observability
**Related:** `.specify/memory/constitution.md`, [[0007-proposal-aware-status]] (a concrete instance
of the gap), Principle I (Silicon Truth), Principle IV (Manager is a Transient Viewer)

## The gap

The constitution has eight principles about where truth *lives* and how it stays coherent
(Silicon Truth, Sovereign Identity, Intrinsic State, Transient Viewer, One-DB, Federated Authority,
Logical Datasets, Transform-the-Constraint). It says a great deal about **correctness** and almost
nothing about **observability** — the operator's ability to *see the state of the system and what
needs doing*.

Principle I (Silicon Truth) is the closest: it demands that what we report be the *observed* truth,
never a cached claim. But that governs the **honesty** of a status we choose to show — it does not
require that the system **make its state and outstanding work visible in the first place**. A
system can be perfectly truthful and still opaque: it answers correctly only about the questions
you knew to ask.

[[0007-proposal-aware-status]] is a clean example: `mneme mp status` was *honest* about each
campaign's index/config (Principle I satisfied), yet a whole class of outstanding work — the
proposal branches awaiting integration — was simply invisible, because nothing in the doctrine said
"the pending work must be discoverable, not remembered." We caught it by use, not by principle.

## What to consider (when we pick this up)

A candidate ninth principle — *Observability / Legibility* — something like:

> **The state of the system, and the work outstanding against it, must be discoverable from the
> system itself — not held in an operator's memory.** It is not enough to answer honestly when
> asked (Principle I); the system must surface *what to ask*: what is drifted, what is pending,
> what decision is owed. A correct-but-opaque system still forces an expensive human back into the
> loop (cf. "Determinism is Trust"). Prefer one honest "what's true / what's next" view over state
> scattered across logs, branches, and tribal knowledge.

Open questions to resolve before amending:

- Is this a **new principle** or an **expansion of Principle I** (from "report honestly" to
  "report honestly *and* completely / surface the to-do")?
- The "On this platform" clause: `hypostasis status` + `mneme mp status` as the single honest
  state+to-do surface; pending proposals, undispositioned divergences, stale indexes, and render
  drift all visible in one place.
- Which anti-pattern does it kill? Provisional: **Opacity / Tribal State** — state that is correct
  but only knowable by someone who already knows where to look.
- Amendment mechanics per Governance: rationale, version bump (MINOR — new/expanded principle),
  and a re-check that the Spec Kit templates + `CLAUDE.md` still agree.

## Why deferred

Feature 002 is mid-flight; amending the constitution mid-feature would churn the gates every
in-flight spec/plan is checked against. Land 002 first (it already *practices* observability via
[[0007-proposal-aware-status]]), then ratify the principle so future features inherit it.
