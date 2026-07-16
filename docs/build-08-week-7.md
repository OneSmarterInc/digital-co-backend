# Build 08 Week 7

Week 7, "The Squeeze," is the first delayed-consequence payoff week. Earlier
cloud and integrator choices now shape the severity of the vendor crisis, while
the Week 7 response is scored on how well the team handles the inherited
conditions.

## Implemented

- Week 7 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 7
- `wk4_cloud_commitment()` derivation helper for later lock-in consumers
- centralized Week 7 scoring, relationship, and OT hardening constants
- vendor-squeeze scoring that separates inherited severity from current-week
  response quality
- `hedge_begun` flag write for later cloud-lock-in resolution
- OT gate closure in `finalize_state_update()` using instructor-confirmed signal
  handling

## Foundation Discipline

Build 08 does not introduce a new OT state vocabulary. The Week 7 specification's
`built | partial | neglected` prose is derived from the existing canonical
`through_lines.security_ot.posture` and `through_lines.security_ot.neglect`
counters. The gate write remains `gates.security_ot`.

Cloud severity is read through the shared `squeeze_severity()` helper. Week 7
uses that severity to shape the scenario and components, while scoring still
evaluates the current response.

## Verified

Tests cover the standard Week 7 lifecycle, low versus high lock-in severity,
renegotiation leverage from Week 4 position, OT gate closure, state reload
persistence, end-to-end Weeks 1-7 decision-history continuity, no-spoiler
student-facing text, contract shape, and the Week 4 cloud-commitment derivation.
