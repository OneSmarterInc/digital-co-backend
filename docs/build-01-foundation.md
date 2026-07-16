# Build 01 Foundation v2

This build implements the architecture spine only. Real Week 1 and Week 2
content should be added later as `WeekModule` plugins. Any shared state fields
discovered while building those modules should be added to `core.state` and
migrated through the foundation.

## Build Sequence Mapping

1. Skeleton: `core.models`, `core.state`, admin registration, and migrations.
2. Engine flow: `engine.services` and the stub module lifecycle.
3. Advisor service: `advisors.llm_client`, prompt assembly, conversations, and
   persisted messages.
4. WeekModule contract: `weeks.modules`, `weeks.structures`, and `weeks.registry`.
5. Scoring engine: `scoring.services`, `ScoreRecord`, benchmarks,
   `scoring.config`, `engine.derivations`, and `engine.climax`.
6. Two-tier dial: `Cohort.tier` flows into advisor prompts, briefing explicitness,
   and rubric variants.
7. Web layer: minimal student briefing, consultation, submission, and instructor
   scoring views.
8. Benchmarks: phase snapshots after weeks 4, 8, 11, and 14 with gated reveal.

## State Contract

`Run.state` is a versioned JSON document. The current schema version is 2.
Use helpers in `core.state` for default creation, validation, decision history
appends, flags, notes, and irreversible gate movement.

The security gate is `gates.security_ot`. The previous `gates.ot_security` name
is invalid in v2 and is migrated by `core.0002_run_state_schema_v2`.

`core.state` validates:

- `cloud_lockin.state`: `unset`, `locked`, `broken`
- `data_rights.posture`: `unset`, `open_unresolved`, `scoped`, `closed`,
  `contested_aggressive`
- `security_ot.posture` and `security_ot.neglect` as non-negative counters
- coherence drift event shape
- the named flags catalog and known enum values

Do not add a standalone `board_confidence` field. Board mood is derived through
`engine.climax.board_receptiveness` from accumulated scores, gates,
relationships, and outcomes.

## Derivations

Week modules should call shared helpers in `engine.derivations` and
`engine.climax` rather than walking `decision_history` or re-implementing climax
logic. The foundation includes prior-decision accessors, severity derivations,
`arc_coherence`, `board_receptiveness`, `resolve_endgame`,
`generate_debrief`, trace helpers, and `accumulated_scars`.

`resolve_endgame` earns a tier from accumulated score, then applies the v2
ceilings:

- `security_ot` detonated caps at `WIN_WITH_SCARS`
- `budget_credibility` closed or detonated caps at `WIN_WITH_SCARS`
- `board_verdict == denied` caps at `SQUEAK_THROUGH`
- `board_verdict == confidence_lost` caps at `DISASTER`

## Week Modules

A week module implements `WeekModule` and is registered in `weeks.registry`.
Modules should expose declarative briefing, artifacts, advisor context, and
decision specs, plus hooks for deterministic scoring and state updates.

## Benchmarks

Benchmarks are per-phase:

- Week 4: accumulated score
- Week 8: accumulated score, deliberately omitting the data-rights fuse
- Week 11: accumulated score plus trust factors
- Week 14: Week 11 factors plus resolved tier

## LLM Boundary

Every model call goes through `advisors.llm_client`. The default provider is the
deterministic `echo` client so the application and tests run without a network
provider.
