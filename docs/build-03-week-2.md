# Build 03 Week 2

Week 2, "The Alignment Confrontation," is the first steady-state `WeekModule`.
It proves that the simulation remembers Week 1, reads prior state explicitly, and
propagates new consequences without changing foundation contracts.

The schema refinements mentioned in the Build 03 spec are already satisfied by
Build 01 v2: `through_lines.coherence.anchor_strength`,
`flags.governance_built`, and `flags.calloway_patron`.

## Implemented

- `reads_state()` dependency declaration for Week 1 anchor, coherence state,
  relationships, security/OT state, decision history, and flags
- briefing, artifacts, executive reads, advisor contexts, and decision spec
- centralized Week 2 scoring constants
- shared Week 1 direction derivation and direction comparators in
  `engine.derivations`
- generic engine validation for declared state dependencies
- deterministic scoring for mush, no-governance, Calloway misreads, and
  coherence against the Week 1 direction
- state updates for Calloway patronage, Reinhardt discipline, governance
  persistence, coherence drift events, and Week 2 decision history

## Verified

Tests cover coherence extension, coherence drift, weak-anchor cap, Calloway
patron creation, governance persistence, decision-history append behavior,
relationship updates, and a Week 1 -> Week 2 lifecycle. They also prove that two
different Week 1 outcomes produce different Week 2 coherence behavior.
