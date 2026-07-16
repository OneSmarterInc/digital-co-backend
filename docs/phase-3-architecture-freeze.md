# Phase 3 Architecture Freeze

Build 12 closes the architecture validation phase. Weeks 12-14 should primarily
consume the established model rather than introduce new framework structures.

## Canonical State

`Run.state` remains the source of cross-week truth:

- `through_lines.security_ot`
- `through_lines.cloud_lockin`
- `through_lines.data_rights`
- `through_lines.coherence`
- `gates.security_ot`
- `gates.budget_credibility`
- `relationships`
- `flags`
- `decision_history`
- `accumulated_scores`

Facts are stored once. Higher-level meaning is derived.

## Derivation Helpers

The engine derivation layer turns state into scenario conditions:

- `derive_wk1_direction`
- `wk4_differentiator`
- `wk4_cloud_commitment`
- `wk8_rights_posture`
- `squeeze_severity`
- `breach_severity`
- `convergence_severity`
- `repair_ceiling`
- `derive_data_rights_trace`

Week modules should call these helpers instead of re-parsing history locally
when the logic is shared or cross-cutting.

## WeekModule Contract

Every week remains a plugin implementing:

- `reads_state()`
- `briefing()`
- `artifacts()`
- `advisor_context()`
- `decision_spec()`
- `score_auto()`
- `apply_state_update()`
- optional `finalize_state_update()`

Weeks own scenario content and local scoring. Shared state interpretation lives
in `engine/derivations.py`.

## Gate Model

Gates change inherited conditions and endgame ceilings. They are not simple point
deductions.

- `budget_credibility` closes in Week 3 and affects standing/endgame.
- `security_ot` closes in Week 7 and detonates in Week 10.

## Benchmark Model

Benchmarks are read-only projections over run state:

- Week 4: accumulated score and visible Phase 1 effects
- Week 8: accumulated score only
- Week 11: accumulated score plus trust/data advantage
- Week 14: final outcome and resolved tier

Benchmarks never mutate `Run.state`.

## Instructor Trace Model

Instructor/internal explainability is computed, not stored. Week 11 establishes
the pattern with `derive_data_rights_trace(state)`, proving:

canonical state -> derivations -> crisis severity -> scenario conditions

Student-facing content reveals the crisis, not the engine internals.

## Causal Threads

Validated cross-week threads:

- Week 1-2 coherence and governance
- Week 3-4-7-12 cloud lock-in
- Week 1-7-10 security/OT gate
- Week 6-8-10-11 data rights and trust
- Week 8-9 predictive capability
- Week 9-10-11 shadow AI

Future builds should extend these threads only through canonical state and
shared derivations unless a true reusable contract gap appears.
