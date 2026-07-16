# Build 04 Week 3

Week 3, "The Reckoning," is the first project-crisis module and the first week
to create a long-dormant consequence. It consumes the established foundation
contracts rather than reshaping them.

## Implemented

- Week 3 `reads_state()` declaration for S/4 precommitment, Week 2 governance,
  relationship balances, decision history, coherence state, and the
  `budget_credibility` gate
- briefing, artifacts, executive reads, advisor contexts, and decision spec
- deterministic scoring for sunk-cost push-through, integrator lifeline,
  blame-shifting, governance use, and conditional coherence misallocation
- long-fuse state writes:
  - `flags.integrator_accelerator_taken`
  - `through_lines.cloud_lockin.depth`
  - cloud-lockin note
  - Week 3 decision history
- grading-time state update hook for human-judged `plan_sound`
- budget credibility gate closure when money is thrown without a sound plan
- Reinhardt conversion/loss at grading

## Verified

Tests cover sound handling, governance use, absent governance penalty, accelerator
persistence after database reload, budget gate closure, conditional coherence
penalty, decision-history append behavior, and Week 3 contract shape.
