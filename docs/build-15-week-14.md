# Build 15 Week 14

Week 14, "The Synthesis," closes DigitalCo. It resolves the endgame, generates
the team debrief, and completes the final benchmark.

## Implemented

- Week 14 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, state update, and post-grading finalization
- registry and data migration for Week 14
- centralized Week 14 scoring constants
- richer derived `generate_debrief(state)` output with coherence, lock-in,
  data-rights, security, and leadership traces
- final benchmark exposure of the resolved tier
- final run completion through the existing scoring service

## Finale Rules

Week 14 does not add a new architecture layer. It consumes:

- accumulated scores
- gate ceilings
- Week 13 board verdict
- settled arc coherence
- named flags
- through-lines
- relationships
- decision history

The synthesis scores three final dimensions:

- whether the integration is genuine or papered over
- whether the reckoning honestly owns accumulated scars
- whether the forward strategy is grounded in the position actually built

Because Week 14 scoring is merged after submission, the module writes a
provisional endgame/debrief at submission and recomputes the final derived
outputs in `finalize_state_update()` after all Week 14 scores are accumulated.

## Verified

Tests cover Week 14 lifecycle, final run completion, benchmark tier exposure,
the victory-narrative trap, weak-arc integration denial, contract shape, and
deterministic regeneration of the endgame and debrief after save/reload.
