# DigitalCo Build 01 - Foundation

Build 01 is the generic engine spine for DigitalCo. It does not implement Week 1
content. Weeks are plugins that implement `weeks.modules.WeekModule` and read or
write cross-week state only through `Run.state`.

## Apps

- `core`: users, cohorts, teams, runs, enums, and canonical state helpers.
- `weeks`: week definitions, week instances, submissions, typed module contract,
  registry, and a stub module used to prove the lifecycle.
- `advisors`: advisor definitions, conversations, messages, prompt assembly, and
  the provider-agnostic `llm_client`.
- `engine`: lifecycle services for briefing, consultation, submission, shared
  derivation helpers, and climax/endgame functions.
- `scoring`: two-track score merge, accumulated scores, endgame config, and
  benchmarks.
- `web`: minimal student and instructor flows.

## Build 01 Contract

The foundation supports this lifecycle:

`BRIEFING -> CONSULTATION -> SUBMITTED -> SCORED`

The canonical state contract is schema version 2. The security gate is
`gates.security_ot`, matching `through_lines.security_ot`; the old
`gates.ot_security` name is invalid. The foundation also validates the shared
through-line state machines and the named flags catalog needed by later week
modules. There is no separate `board_confidence` scalar.

All tunable values live in `scoring.config`. All model calls must go through
`advisors.llm_client.get_llm_client()`. Shared state additions discovered in later
week builds should be folded back into `core.state` rather than implemented as
week-local structures. Benchmarks are phase-specific: weeks 4 and 8 rank by
accumulated score, week 11 adds trust factors, and week 14 adds the resolved tier.

## Local Commands

```powershell
python manage.py migrate
python manage.py test
python manage.py runserver
```

The default LLM provider is `echo`, a deterministic local implementation intended
for tests and development.
