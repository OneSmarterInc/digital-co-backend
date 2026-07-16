# Build 14 Week 13

Week 13, "The Audit," is the organizational judgment week. The board evaluates
the accumulated record, not the presentation in isolation.

## Implemented

- Week 13 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 13
- centralized Week 13 scoring constants
- `board_receptiveness(state)` refined to read the accumulated organizational
  record
- `arc_coherence()` used to settle the coherence through-line
- `board_verdict` and `arc_coherence_settled` writes for Week 14

## Board Judgment

Week 13 separates the accumulated room from the current presentation:

- `board_receptiveness(state)` reads relationships, gates, trust, data
  advantage, breach outcome, infrastructure sustainability, lock-in learning,
  execution, and coherence drift.
- Deck quality determines whether the team can meet the room it earned.
- A clean deck into a supportive board can be granted.
- A weak deck into a supportive board can still be denied.
- A strong deck into a skeptical board can be denied because the record is not
  strong enough.
- A competent deck into a hostile board can lose confidence entirely.

## Verified

Tests cover the four verdict interactions, incoherence reckoning, end-to-end
Weeks 1-13 continuity, board verdict writes, arc settlement, and registry
contract shape.
