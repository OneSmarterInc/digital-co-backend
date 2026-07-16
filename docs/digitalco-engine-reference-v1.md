# DigitalCo Engine Reference v1

This reference freezes the completed DigitalCo v1 engine after Build 15. Future
scenarios should plug into these contracts rather than redesigning the spine.

## Canonical State

`Run.state` is the source of cross-week truth. Facts are stored once; business
meaning is derived.

- `schema_version`
- `coherence_anchor`
- `accumulated_scores`
- `gates.security_ot`
- `gates.budget_credibility`
- `through_lines.security_ot`
- `through_lines.cloud_lockin`
- `through_lines.data_rights`
- `through_lines.coherence`
- `relationships`
- `decision_history`
- `flags`
- terminal `debrief`

The security gate is `security_ot`. There is no `ot_security` gate and no
separate `board_confidence` scalar.

## WeekModule Contract

Weeks are plugins that implement:

- `reads_state()`
- `briefing(tier)`
- `artifacts(tier)`
- `advisor_context(advisor_key, tier, run_state)`
- `decision_spec(tier)`
- `score_auto(submission, run_state)`
- `apply_state_update(submission, auto, run_state)`
- optional `finalize_state_update(score_record, run_state)`

Week modules own scenario content and local scoring. Shared interpretation of
history belongs in the engine derivation layer.

## Derivation Catalog

Shared helpers convert canonical state into reusable business meaning:

- `derive_wk1_direction`
- `contradicts`
- `extends`
- `wk4_differentiator`
- `wk4_cloud_commitment`
- `wk4_took_sweet_deal`
- `wk8_rights_posture`
- `squeeze_severity`
- `breach_severity`
- `convergence_severity`
- `repair_ceiling`
- `derive_data_rights_trace`
- `arc_coherence`
- `board_receptiveness`
- `resolve_endgame`
- `generate_debrief`

New helpers should be added only when more than one week or a cross-cutting
engine view needs the same interpretation.

## Gate Model

Gates are inherited conditions and endgame ceilings, not simple deductions.

- `budget_credibility` can close in Week 3 and caps the endgame at
  `WIN_WITH_SCARS`.
- `security_ot` can close in Week 7, detonate in Week 10, and caps the endgame
  at `WIN_WITH_SCARS` when detonated.
- `board_verdict == denied` caps the endgame at `SQUEAK_THROUGH`.
- `board_verdict == confidence_lost` caps the endgame at `DISASTER`.

## Benchmark Model

Benchmarks are read-only projections over state and never mutate `Run.state`.

- Week 4: accumulated score
- Week 8: accumulated score only
- Week 11: accumulated score plus trust/data advantage
- Week 14: accumulated score, trust/data advantage, and resolved tier

Student-facing benchmark payloads reveal standing and visible outcomes, not
hidden causal machinery.

## Through-Line Model

Validated through-lines include:

- coherence: Week 1 anchor through Week 13 audit and Week 14 synthesis
- cloud lock-in: Weeks 3, 4, 7, 9, and 12
- security/OT: Weeks 1, 7, 10, and the endgame ceiling
- data rights and trust: Weeks 6, 8, 10, and 11
- predictive capability: Weeks 8 and 9
- board credibility: relationships, gates, trust, learning, and execution

## Causal Trace Model

Instructor/internal explainability is derived, not stored as separate narrative
state. `generate_debrief(state)` reads canonical state and returns deterministic
traces for:

- coherence
- lock-in
- data rights
- security
- leadership

The student experience reveals consequences and lessons. The instructor view can
trace those consequences back to ordinary accumulated state.

## Endgame Model

`resolve_endgame(state, auto=None)` computes the earned tier from accumulated
scores and then applies ceilings from gates, board verdict, and weak anchor
conditions. `generate_debrief(state)` explains that result from the same record.

Week 14 finalization recomputes the tier and debrief after final grading so the
stored run outcome, final benchmark, and debrief all reflect the complete
fourteen-week record.

## Extension Rules

- Do not add parallel state for facts already represented in canonical state.
- Add named flags to the catalog when they become shared memory.
- Put tunable constants in centralized scoring config.
- Keep provider calls behind the provider-agnostic LLM client.
- Keep benchmark projections read-only.
- Keep hidden future consequences out of student-facing payloads until they are
  narratively visible.
- Prefer derived traces over stored explanatory narratives.
