# Build 12 Week 11

Week 11, "The Reckoning of Trust," is the convergence crisis. It proves that
the simulation can explain a major crisis entirely from accumulated state:
Week 6 openness, Week 8 rights posture, Week 10 fleet impact, Ferraro/Tran
relationships, shadow-AI state, and coherence history.

## Implemented

- Week 11 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 11
- centralized Week 11 scoring constants
- `wk8_rights_posture()` now reads the Week 8 decision-history entry
- `derive_data_rights_trace(state)` computes an instructor/internal trace from
  canonical state
- `data_advantage` and `trust_state` writes for Weeks 13 and 14
- Phase 3 benchmark generation after Week 11

## Convergence Discipline

No Week 11-specific bridge state was added. The crisis is derived from ordinary
accumulated state:

- `through_lines.data_rights.posture`
- `flags.fleet_impact`
- `flags.shadow_ai_incident_open`
- `relationships.ferraro`
- `relationships.tran`
- `through_lines.coherence.drift_events`
- `decision_history`

The instructor trace is computed on demand and included in auto-score components;
it is not persisted as a separate narrative object.

## Credibility Scoring

The same `shared_value` resolution scores differently depending on prior
history. A team extending a Week 8 shared-value posture receives full credit. A
team pivoting from a prior land grab receives partial credit and a `late_pivot`
flag, because the organization has not earned the same credibility.

## Verified

Tests cover Week 11 lifecycle, full-credit shared value, late pivot after a land
grab, hold-firm/concede consequences, exact trace regeneration after reload,
student-facing no-trace output, end-to-end Weeks 1-11 continuity, Week 11
benchmark generation, and registry contract shape.
