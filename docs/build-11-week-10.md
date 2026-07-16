# Build 11 Week 10

Week 10, "The Breach," is the security/OT gate detonation. It proves that
`gates.security_ot` changes the breach condition the team inherits, not merely
the score they receive for the week.

## Implemented

- Week 10 module with briefing, artifacts, advisor contexts, decision spec,
  deterministic scoring, and state updates
- registry and data migration for Week 10
- centralized Week 10 scoring constants
- breach severity derived from `gates.security_ot`, `through_lines.security_ot`,
  and `shadow_ai_incident_open`
- gate detonation through `gates.security_ot = detonated`
- breach flags:
  - `breach_contained`
  - `breach_catastrophic`
  - `fleet_impact`
- fleet-compromise notes added to `through_lines.data_rights` for Week 11

## Gate Discipline

Week 10 separates inherited condition from current performance:

- The OT gate and accumulated posture determine breach severity and visibility.
- Week 10 scoring evaluates containment, disclosure, triage, and reasoning.
- The ransom decision is recorded but not scored as pay-versus-refuse.

A team can respond well from a catastrophic inherited position, but the gate
still detonates and preserves the endgame ceiling consequence.

## Verified

Tests cover open versus closed gate severity, prior OT posture and visibility,
shadow-AI compounding, state reload stability, linear/spin response penalties,
end-to-end Weeks 1-10 continuity, gate detonation, fleet-impact writes,
decision-history append behavior, and registry contract shape.
