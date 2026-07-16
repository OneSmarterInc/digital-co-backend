# Build 05 Week 4

Week 4, "The Foundation," closes Phase 1. It proves that the simulation can
write hidden lock-in pressure, compute the first benchmark as a read-only
projection, and reveal comparative standing without exposing future causal
machinery.

## Implemented

- Week 4 `reads_state()` for coherence state, decision history, budget
  credibility, cloud lock-in, integrator accelerator flag, and relationships
- briefing, artifacts, executive reads, advisor contexts, and decision spec
- deterministic scoring for sweet-deal lock-in, build-everything,
  starved-differentiator, negotiation discipline, and sourcing coherence
- cloud-lockin state writes:
  - sweet deal sets `cloud_lockin.state = locked`
  - sweet deal increases `cloud_lockin.depth`
  - protected/multi-vendor paths avoid the locked state
- Fischer and Reinhardt relationship updates
- Week 4 decision-history append
- Phase 1 benchmark computation after Week 4 finalization
- student-facing benchmark payload that excludes hidden state and future-spoiler
  language

## Benchmark Discipline

The benchmark is a projection over run state. It writes only the `Benchmark`
snapshot and never mutates `Run.state`.

Student-facing benchmark output omits hidden causal machinery such as
`cloud_lockin`, lock-in notes/depth, trap flags, future week references, and
internal gate metadata. Instructor/admin state inspection still retains the full
state record.

## Verified

Tests cover Week 4 lifecycle, cloud-lockin state/depth updates, benchmark
generation, benchmark reveal gating, budget credibility comparison, hidden
state persistence, no-spoiler benchmark serialization/rendering, and
decision-history append behavior.
