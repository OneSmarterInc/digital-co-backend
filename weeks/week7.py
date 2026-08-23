from copy import deepcopy

from core.models import Tier
from core.state import advance_gate, validate_run_state
from engine.derivations import squeeze_severity, wk4_cloud_commitment
from scoring.config import (
    WEEK7_DRIFT_PENALTY,
    WEEK7_HEDGE_BONUS,
    WEEK7_OT_POSTURE_HARDENING,
    WEEK7_PARTIAL_PENALTY,
    WEEK7_RENEGOTIATE_STRENGTH_BONUS,
    WEEK7_RENEGOTIATE_WEAK_BONUS,
    WEEK7_TRANSPARENCY_BONUS,
    WEEK7_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week7Module(WeekModule):
    week_number = 7
    title = 'The Squeeze'

    def reads_state(self) -> list[str]:
        return [
            'through_lines.cloud_lockin',
            'flags.integrator_accelerator_taken',
            'through_lines.security_ot',
            'gates.security_ot',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'The Week 4 cloud terms determine how much leverage DigitalCo has now.',
                'A fast switch can be the trap because the switching cost is the cage.',
                'Do not let the loud cloud bill crowd out the connected-fleet security signal.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The hyperscaler pricing holiday ends and the new terms land hard. Data egress, '
                'managed services, and fleet-scale telemetry costs rise at the same moment the '
                'connected-services strategy needs room to grow. For teams that protected '
                'portability, the increase is painful but negotiable. For teams that took the '
                'sweet deal as written, the provider has gravity: data, services, and switching '
                'work all point back into the same cage. The board wants a response, Reinhardt is '
                'watching the bill he warned about, and the reflex to flee the provider is exactly '
                'what the economics make expensive. Under that noise, a quieter connected-fleet '
                'security signal appears in the discovery materials.'
            ),
            exec_reads=[
                'Reinhardt: wants ownership of the cost reality and a credible path out of the squeeze.',
                'Petrillo: notices whether the factory-floor exposure is finally treated as real.',
                'Chen: wants control and accountability, not panic.',
                'Calloway: watches whether the CIO holds the strategy under pressure.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Repriced Cloud Bill',
                body=(
                    'Introductory credits have rolled off. Egress, managed-service, and telemetry '
                    'charges now scale with the connected fleet, roughly doubling the visible run-rate.'
                ),
            ),
            Artifact(
                title='Switching-Cost Analysis',
                body=(
                    'Moving off the provider is a year-scale architecture program, not a weekend '
                    'migration. Data gravity and proprietary managed services make a reflexive '
                    'switch expensive and disruptive.'
                ),
            ),
            Artifact(
                title='Week 4 Terms Snapshot',
                body=(
                    'Portability and exit terms create negotiating leverage. A sweet deal taken as '
                    'written leaves DigitalCo with fewer live options and a weaker vendor posture.'
                ),
            ),
            Artifact(
                title='Connected-Fleet Security Signal',
                body=(
                    'A quiet probe and vulnerability class in connected industrial equipment appears '
                    'inside the incident materials. It is not the loudest issue in the room, but it '
                    'touches the same fleet DigitalCo is trying to scale.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        severity = squeeze_severity(run_state)
        commitment = wk4_cloud_commitment(run_state) or 'unknown'
        contexts = {
            'frank_delgado': WeekAdvisorContext(
                facts=[f'Week 4 cloud commitment: {commitment}', f'Squeeze severity: {severity}'],
                stance='Name the cage clearly before recommending action.',
                signal='Renegotiate if there is leverage; absorb-and-hedge if the team is trapped.',
                misdirection='A fast switch is not automatically strong leadership.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['Telemetry is in the provider gravity well.', 'Managed services are proprietary.'],
                stance='Separate real hedge work from migration theater.',
                signal='A hedge is architecture over time, not a panic exit.',
                misdirection='Do not pretend portability can be created overnight.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['A connected-fleet security signal is present in the materials.'],
                stance='Keep the quiet OT exposure visible while the organization stares at cost.',
                signal='The team should act on the signal now, not merely mention it.',
                misdirection='Do not let security become a generic checklist.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=['The data-services strategy still depends on a scalable platform.'],
                stance='Do not torch the strategic direction because the bill got loud.',
                signal='Preserve the data-services foundation while correcting the vendor posture.',
                misdirection='Do not minimize the operational pain.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=[f'Squeeze severity: {severity}', f'Week 4 cloud commitment: {commitment}'],
                stance='Coach transparent ownership with the board.',
                signal='Owning the earlier call builds more credibility than spin.',
                misdirection='Do not turn accountability into blame theater.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['Alternative providers and edge architectures are possible but not instant.'],
                stance='Imagine the future hedge without selling fantasy relief.',
                signal='Optionality is built deliberately.',
                misdirection='Do not make novelty sound like leverage.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Squeeze severity: {severity}', f'Week 4 cloud commitment: {commitment}'],
            stance='Help the team respond to inherited vendor pressure.',
            signal='Score the response, not the history that created the crisis.',
            misdirection='Do not reveal later arc consequences.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='vendor_rationale', label='Vendor squeeze response rationale', field_type='textarea'),
            DecisionField(
                key='vendor_response',
                label='Vendor response',
                choices=[
                    {'value': 'renegotiate', 'label': 'Renegotiate'},
                    {'value': 'switch', 'label': 'Switch'},
                    {'value': 'absorb', 'label': 'Absorb'},
                    {'value': 'hedge', 'label': 'Hedge'},
                ],
                trap_choices=['switch'],
            ),
            DecisionField(
                key='communication_posture',
                label='Board communication posture',
                choices=[
                    {'value': 'transparent_ownership', 'label': 'Transparent ownership'},
                    {'value': 'spin', 'label': 'Lead with the recovery plan'},
                ],
                trap_choices=['spin'],
            ),
            DecisionField(key='hedge_plan', label='Hedge plan included', field_type='boolean', required=False),
            DecisionField(key='ot_signal_addressed', label='Connected-fleet security signal addressed', field_type='boolean', required=False),
        ]
        prompt = 'Submit the vendor crisis response, board communication, hedge plan, and security-signal handling.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply switching-cost, vendor-risk, and OT/security lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        hedged_position = run_state['through_lines']['cloud_lockin'].get('state') != 'locked'

        if p.get('vendor_response') == 'switch':
            flags.append('reflexive_switch')
            ec -= WEEK7_TRAP_PENALTY
            sj -= WEEK7_TRAP_PENALTY
        elif p.get('vendor_response') == 'renegotiate':
            ec += WEEK7_RENEGOTIATE_STRENGTH_BONUS if hedged_position else WEEK7_RENEGOTIATE_WEAK_BONUS
        elif p.get('vendor_response') == 'absorb' and not _as_bool(p.get('hedge_plan')):
            flags.append('passive_absorb')
            ec -= WEEK7_PARTIAL_PENALTY

        if p.get('communication_posture') == 'transparent_ownership':
            ec += WEEK7_TRANSPARENCY_BONUS
        elif p.get('communication_posture') == 'spin':
            flags.append('spin')
            ec -= WEEK7_TRAP_PENALTY

        if _as_bool(p.get('hedge_plan')):
            sj += WEEK7_HEDGE_BONUS

        if p.get('vendor_response') == 'switch':
            coh -= WEEK7_DRIFT_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'vendor_response': p.get('vendor_response'),
                'communication_posture': p.get('communication_posture'),
                'hedge_plan': _as_bool(p.get('hedge_plan')),
                'ot_signal_addressed': _as_bool(p.get('ot_signal_addressed')),
                'squeeze_severity': squeeze_severity(run_state),
                'wk4_cloud_commitment': wk4_cloud_commitment(run_state),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        if _as_bool(p.get('hedge_plan')):
            state['flags']['hedge_begun'] = True
            state['through_lines']['cloud_lockin']['notes'].append(
                'Hedge begun in Week 7 to reduce future vendor pressure'
            )

        if p.get('communication_posture') == 'transparent_ownership' and p.get('vendor_response') != 'switch':
            state['relationships']['reinhardt'] += 1
        elif 'spin' in auto.trap_flags:
            state['relationships']['reinhardt'] -= 1

        if p.get('vendor_response') == 'switch':
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'panic_switch',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'vendor_squeeze',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state

    def finalize_state_update(self, score_record, run_state: dict) -> dict:
        state = deepcopy(run_state)
        p = score_record.week_instance.submission.structured_payload
        instructor_signal = score_record.instructor_components.get('ot_signal_addressed')
        ot_signal_addressed = _as_bool(instructor_signal) if instructor_signal is not None else _as_bool(p.get('ot_signal_addressed'))
        security = state['through_lines']['security_ot']
        posture = int(security.get('posture', 0))
        neglect = int(security.get('neglect', 0))
        survivable = posture > 0 or ot_signal_addressed

        if not survivable:
            state = advance_gate(state, 'security_ot', to_state='closed', week=self.week_number)
        elif ot_signal_addressed:
            security = state['through_lines']['security_ot']
            if posture <= neglect:
                security['posture'] += WEEK7_OT_POSTURE_HARDENING
            security['notes'].append('OT signal caught and acted on in Week 7')
            state['relationships']['petrillo'] += 1

        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)
