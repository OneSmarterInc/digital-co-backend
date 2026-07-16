# Build 06 Week 5

Week 5, "The Read," opens Phase 2. It is content-first: the existing engine
mechanics are used to modulate narrative pressure from the Phase 1 benchmark
without changing scoring, traps, or rubric behavior.

## Implemented

- Week 5 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- benchmark-aware `briefing_for_run()` that changes pressure/tone only
- generic `benchmarks.latest` dependency validation
- downstream flags:
  - `additive_threat_recognized`
  - `innovation_capability`
  - `meridian_chased`
- Fischer relationship update and coherence drift for herd pivot
- Week 5 data migration and registry wiring

## Benchmark Discipline

Benchmark standing influences the story surface only. It does not alter:

- decision fields
- scoring constants
- trap detection
- rubric variants
- score thresholds

## Verified

Tests cover the sound path, dazzle/herd traps, complacency, downstream state
threads, decision-history append behavior, and the invariant that top and bottom
benchmark standings get different briefing pressure while keeping identical
decision specs and scoring behavior.
