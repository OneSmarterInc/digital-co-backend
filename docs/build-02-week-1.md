# Build 02 Week 1

Week 1, "The Inheritance," is the first real `WeekModule` built on the frozen
Build 01 v2 foundation. It does not introduce new foundation contracts.

The relationship schema refinement mentioned in the Build 02 spec is already
satisfied by Build 01 v2 through `Run.state.relationships`; no schema revision
was added for Week 1.

## Implemented

- `briefing(tier)` with undergrad scaffolding cues
- four discovery artifacts
- six Week 1 advisor contexts
- Week 1 decision spec, including assessment, strategy statement, structured
  choices, OT engagement, and stakeholder anchor
- deterministic `score_auto` for the three traps and sound path
- `apply_state_update` seeding the coherence anchor, security/OT through-line,
  relationships, flags, cloud-lockin note, and decision history
- Week 1 registry and data migration wiring

## Traps

- `kill_connected_products`
- `commit_s4_blind`
- `ferraro_capture`

## Verified

The test suite covers the sound path, all three traps, coherence anchor creation,
security/OT posture and neglect seeding, relationship updates, decision history,
advisor prompt context, and the full lifecycle through scoring.
