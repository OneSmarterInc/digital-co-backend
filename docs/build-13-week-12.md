# Build 13 Week 12

Week 12, "The Reckoning of Cost," resolves the cloud lock-in through-line and
introduces the first explicit organizational-learning evaluation: did the team
recognize a pattern it had already lived through?

## Implemented

- Week 12 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 12
- centralized Week 12 scoring, coherence, negotiation, and lock-in constants
- did-they-learn scoring using `wk4_took_sweet_deal(state)`
- `infra_sustainable` and `lockin_lesson` writes for the endgame
- cloud lock-in resolution through `through_lines.cloud_lockin.state = broken`
- committed-spend re-trap deepens `through_lines.cloud_lockin.depth`

## Learning Test

Week 12 compares Week 4 history with Week 12 behavior:

- Week 4 sweet deal + Week 12 committed-spend discount writes
  `lockin_lesson = not_learned`.
- Week 4 sweet deal + Week 12 edge/repatriation and refusal of the discount
  writes `lockin_lesson = learned`.

This is a meta-evaluation over the decision history, not a new gate or schema.

## Verified

Tests cover the sound path, the learned/not-learned distinction, renegotiation
leverage from the Week 7 hedge, data-gravity traps, cloud-lock-in resolution,
committed-spend depth increase, end-to-end Weeks 1-12 continuity, and registry
contract shape.
