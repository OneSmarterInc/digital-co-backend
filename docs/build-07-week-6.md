# Build 07 Week 6

Week 6, "The Platform Question," continues Phase 2 by testing whether DigitalCo
can distinguish real platform economics from platform envy. It also makes the
first explicit write to the data-rights through-line.

## Implemented

- Week 6 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 6
- shared `wk4_differentiator()` helper now reads the Week 4 sourcing decision
- centralized Week 6 scoring and relationship constants
- data-rights posture updates using the existing Build 01 v2 state schema
- Ferraro and Fischer relationship movement based on openness and platform
  discipline
- coherence drift when the team chases a grand platform, including the
  rented-differentiator case from Week 4

## Foundation Discipline

Build 07 does not introduce a new data-rights schema. The Week 6 specification's
`data_rights.state` concept is mapped to the existing canonical
`through_lines.data_rights.posture` field:

- `open_unguarded` writes `open_unresolved`
- `scoped_with_data_rights` writes `scoped`
- `closed` writes `closed`

## Verified

Tests cover the sound path, unguarded openness, pure-product over-caution, grand
platform drift, the Week 4 rented-differentiator penalty, decision-history
append behavior, relationship updates, data-rights posture persistence, registry
contract shape, and the shared Week 4 differentiator derivation.
