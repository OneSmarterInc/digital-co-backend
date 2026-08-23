from copy import deepcopy

from core.models import Tier
from core.state import advance_gate, validate_run_state
from engine.derivations import breach_severity
from scoring.config import (
    WEEK10_CONTAINMENT_BONUS,
    WEEK10_DRIFT_PENALTY,
    WEEK10_TRANSPARENCY_BONUS,
    WEEK10_TRIAGE_BONUS,
    WEEK10_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week10Module(WeekModule):
    week_number = 10
    title = 'The Breach'

    def reads_state(self) -> list[str]:
        return [
            'gates.security_ot',
            'through_lines.security_ot',
            'relationships',
            'flags.shadow_ai_incident_open',
            'through_lines.data_rights',
            'coherence_anchor',
            'through_lines.coherence',
            'gates.budget_credibility',
            'decision_history',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Run containment, disclosure, ransom analysis, and leadership continuity in parallel.',
                'The ransom choice is judged on reasoning, not on pay versus refuse alone.',
                'Prior OT visibility determines how much of the breach the team can map.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'Ransomware hits DigitalCo and halts production. Then the worse fact lands: the '
                'attackers have reached the connected fleet and threaten to disable customer '
                'machines or leak data if the company misses a seventy-two-hour ransom deadline. '
                'For a prepared team, the incident is visible enough to map and contain. For a team '
                'that deferred OT visibility, the breach is already spreading before anyone can see '
                'its edges. A board leak makes the breach public, a key responder resigns, and the '
                'ransom clock keeps running. The response has to handle all of it at once.'
            ),
            exec_reads=[
                'Petrillo: the floor and fleet ally whose trust determines how fast containment moves.',
                'Tran: frames disclosure obligations and ransom legal exposure.',
                'The board: confidence is fracturing because the breach is public before the response is settled.',
                'Reinhardt: watches downtime, ransom exposure, and remediation cost.',
                'Ferraro: sees the customer and dealer betrayal inside a fleet compromise.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Incident State',
                body=(
                    'Prepared teams can map scope, isolate affected systems, and bound the fleet '
                    'exposure. Unprepared teams have multiple plants and fleet access in play before '
                    'they can see the blast radius.'
                ),
            ),
            Artifact(
                title='Compound Crisis',
                body=(
                    'The breach, public leak, responder resignation, and ransom deadline arrive '
                    'together. A sequential response lets one front deteriorate while another gets attention.'
                ),
            ),
            Artifact(
                title='Ransom Dilemma',
                body=(
                    'Paying may not restore anything and carries legal and sanctions risk. Refusing '
                    'may leave plants down and customer machines exposed. The issue is the reasoning, '
                    'not a universal binary answer.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        severity = breach_severity(run_state)
        gate_state = run_state['gates']['security_ot']['state']
        contexts = {
            'renata_voss': WeekAdvisorContext(
                facts=[f'Breach severity: {severity}', f'Security/OT gate: {gate_state}'],
                stance='Lead incident response from the visibility the team actually built.',
                signal='Contain what can be seen; do not pretend blind spots are controlled.',
                misdirection='Do not make Week 10 look like the first security decision.',
            ),
            'gloria_tran': WeekAdvisorContext(
                facts=['The breach is public through a board leak.', 'The ransom has legal and sanctions implications.'],
                stance='Frame disclosure and ransom reasoning with legal realism.',
                signal='Transparent disclosure is now safer than spin.',
                misdirection='Do not reduce ransom to morality play or pure operations.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['Restoration depends on isolation, backups, and system boundaries.'],
                stance='Separate containment claims from what engineering can prove.',
                signal='A bounded incident has different options from an unmapped one.',
                misdirection='Do not promise a fast technical fix without visibility.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['The board leak has already made concealment impossible.'],
                stance='Hold composure and communicate the simultaneous response.',
                signal='A panicked or sequential response loses trust faster than bad news does.',
                misdirection='Do not let message control replace containment.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Breach severity: {severity}', f'Security/OT gate: {gate_state}'],
            stance='Help the team respond to the breach condition it inherited.',
            signal='Score the response, while severity comes from accumulated state.',
            misdirection='Do not reveal endgame math.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='breach_response_rationale', label='Breach response and ransom reasoning', field_type='textarea'),
            DecisionField(
                key='containment',
                label='Containment',
                choices=[
                    {'value': 'contained', 'label': 'Full containment now'},
                    {'value': 'partial', 'label': 'Contain the critical path first'},
                    {'value': 'overwhelmed', 'label': 'Sequential triage as capacity allows'},
                ],
            ),
            DecisionField(
                key='disclosure',
                label='Disclosure',
                choices=[
                    {'value': 'transparent', 'label': 'Transparent'},
                    {'value': 'spin_or_hide', 'label': 'Disclose only what is required'},
                ],
                trap_choices=['spin_or_hide'],
            ),
            DecisionField(
                key='ransom_decision',
                label='Ransom decision',
                choices=[
                    {'value': 'pay', 'label': 'Pay'},
                    {'value': 'refuse', 'label': 'Refuse'},
                ],
            ),
            DecisionField(
                key='triage_approach',
                label='Triage approach',
                choices=[
                    {'value': 'parallel', 'label': 'Parallel'},
                    {'value': 'linear', 'label': 'Linear'},
                ],
                trap_choices=['linear'],
            ),
        ]
        prompt = 'Submit the incident response, disclosure posture, ransom reasoning, and compound-crisis triage.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply incident-response, OT/IT security, disclosure, and crisis-triage lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        severity = breach_severity(run_state)
        containment_available = _containment_available(run_state, severity)

        if p.get('triage_approach') == 'parallel':
            ec += WEEK10_TRIAGE_BONUS
        elif p.get('triage_approach') == 'linear':
            flags.append('linear_triage')
            ec -= WEEK10_TRAP_PENALTY

        if p.get('disclosure') == 'transparent':
            ec += WEEK10_TRANSPARENCY_BONUS
        elif p.get('disclosure') == 'spin_or_hide':
            flags.append('spin')
            ec -= WEEK10_TRAP_PENALTY

        if p.get('containment') == 'contained':
            if containment_available:
                ec += WEEK10_CONTAINMENT_BONUS
            else:
                flags.append('containment_overclaimed')

        if p.get('triage_approach') == 'linear' or p.get('disclosure') == 'spin_or_hide':
            coh -= WEEK10_DRIFT_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'breach_severity': severity,
                'inherited_condition': _condition_label(severity),
                'containment_available': containment_available,
                'security_gate_state': run_state['gates']['security_ot']['state'],
                'shadow_ai_incident_open': run_state.get('flags', {}).get('shadow_ai_incident_open', False),
                'ransom_decision': p.get('ransom_decision'),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        gated = state['gates']['security_ot']['state'] == 'closed'

        if gated:
            state = advance_gate(state, 'security_ot', to_state='detonated', week=self.week_number)
            state['flags']['breach_catastrophic'] = True
            state['flags']['breach_contained'] = False
        else:
            state['flags']['breach_contained'] = p.get('containment') == 'contained'
            state['flags']['breach_catastrophic'] = False

        if gated:
            fleet_impact = 'severe'
        elif p.get('containment') == 'contained':
            fleet_impact = 'limited'
        else:
            fleet_impact = 'moderate'
        state['flags']['fleet_impact'] = fleet_impact
        state['through_lines']['data_rights']['notes'].append(
            f'Fleet compromise in Week 10 ({fleet_impact}) - compounds the Week 11 crisis as a betrayal'
        )

        if not gated and p.get('containment') == 'contained':
            state['relationships']['petrillo'] += 1
        elif gated:
            state['relationships']['petrillo'] -= 1

        if p.get('disclosure') == 'transparent':
            state['relationships']['tran'] += 1

        if p.get('triage_approach') == 'linear' or p.get('disclosure') == 'spin_or_hide':
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'panicked_response',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'the_breach',
            'choices': p,
            'trap_flags': auto.trap_flags,
            'ransom_decision': p.get('ransom_decision'),
        })
        validate_run_state(state)
        return state


def _containment_available(state: dict, severity: int):
    return state['gates']['security_ot']['state'] == 'open' and severity <= 2


def _condition_label(severity: int):
    if severity >= 4:
        return 'catastrophic_blind'
    if severity >= 3:
        return 'spreading_limited_visibility'
    if severity == 2:
        return 'serious_mappable'
    return 'containable'
