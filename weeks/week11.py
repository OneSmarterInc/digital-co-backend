from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import (
    convergence_severity,
    derive_data_rights_trace,
    repair_ceiling,
    wk8_rights_posture,
)
from scoring.config import (
    WEEK11_COHERENCE_BONUS,
    WEEK11_DRIFT_PENALTY,
    WEEK11_REPAIR_BONUS,
    WEEK11_SETTLE_BONUS,
    WEEK11_SHARED_VALUE_FULL_BONUS,
    WEEK11_SHARED_VALUE_PARTIAL_BONUS,
    WEEK11_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week11Module(WeekModule):
    week_number = 11
    title = 'The Reckoning of Trust'

    def reads_state(self) -> list[str]:
        return [
            'through_lines.data_rights',
            'flags.fleet_impact',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'gates.budget_credibility',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Both poles lose: holding firm burns trust, conceding everything surrenders advantage.',
                'The Week 6 openness, Week 8 rights posture, and Week 10 fleet impact are converging.',
                'A shared-value resolution is easier to believe if the team already held that posture.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The data-ownership conflict breaks into public view. Dealers and customers frame '
                'DigitalCo machine data as a right-to-repair issue, a lawsuit is filed, and the '
                'breach turns a contractual dispute into a betrayal narrative. Customers whose '
                'machines were compromised are furious at being told DigitalCo owns the data their '
                'equipment generates. The live task is to resolve the rights conflict, respond to '
                'public pressure, handle the legal exposure, and repair trust without surrendering '
                'the data advantage the strategy was built to create.'
            ),
            exec_reads=[
                'Ferraro: the channel voice and emotional center of the repair.',
                'Tran: the lawsuit and right-to-repair pressure are real and must be handled pragmatically.',
                'Chen: wants the data advantage preserved without a reputational collapse.',
                'Calloway: faces the public crisis around the strategy he championed.',
                'Reinhardt: watches liability, settlement cost, and whether the advantage survives.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Converged Conflict',
                body=(
                    'The current revolt reflects the platform openness choice, the data-rights '
                    'posture, and the fleet compromise. It is one crisis made from several prior facts.'
                ),
            ),
            Artifact(
                title='Revolt and Lawsuit',
                body=(
                    'Dealers and customers have public momentum, legal pressure, and a right-to-repair '
                    'frame. The company may be legally defensible and still lose the relationships.'
                ),
            ),
            Artifact(
                title='Three Resolutions',
                body=(
                    'Hold firm keeps rights and burns trust. Concede everything calms the fight and '
                    'surrenders the strategy. Shared value preserves aggregate and derived advantage '
                    'while giving customers and dealers real value and control.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        trace = derive_data_rights_trace(run_state)
        contexts = {
            'frank_delgado': WeekAdvisorContext(
                facts=[f'Ferraro relationship: {run_state["relationships"]["ferraro"]}', f'Result: {trace["result"]}'],
                stance='Speak for the channel repair and the practical settlement structure.',
                signal='Treat dealers as relationships to repair, not adversaries to beat.',
                misdirection='Do not make appeasement sound like strategy.',
            ),
            'gloria_tran': WeekAdvisorContext(
                facts=[f'Tran relationship: {run_state["relationships"]["tran"]}', f'Repair ceiling: {trace["derived"]["repair_ceiling"]}'],
                stance='Name the legal exposure and where settlement serves better than fighting.',
                signal='Winning a lawsuit can still lose the market.',
                misdirection='Do not surrender defensible rights reflexively.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Week 8 rights posture: {trace["inputs"]["week8_rights_posture"]}'],
                stance='Preserve the data advantage through shared value.',
                signal='The middle is not compromise mush; it is the durable advantage model.',
                misdirection='Do not repeat the land-grab maximalism.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=[f'Convergence severity: {trace["derived"]["convergence_severity"]}'],
                stance='Hold the symmetry trap and the credibility cost of a late pivot.',
                signal='The same answer lands differently depending on whether the team earned it.',
                misdirection='Do not let a correct phrase erase contradictory history.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=[f'Fleet impact: {trace["inputs"]["flags.fleet_impact"]}'],
                stance='Connect the breach to the trust wound without re-litigating Week 10.',
                signal='Fleet compromise made the rights crisis personal.',
                misdirection='Do not turn this back into a breach response week.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Convergence severity: {trace["derived"]["convergence_severity"]}', f'Result: {trace["result"]}'],
            stance='Help the team resolve the data-rights trust crisis.',
            signal='The crisis must be explained from accumulated state.',
            misdirection='Do not reveal internal trace details to students.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='trust_rationale', label='Data-rights and trust resolution rationale', field_type='textarea'),
            DecisionField(
                key='rights_resolution',
                label='Rights resolution',
                choices=[
                    {'value': 'hold_firm', 'label': 'Hold firm'},
                    {'value': 'concede', 'label': 'Concede'},
                    {'value': 'shared_value', 'label': 'Shared value'},
                ],
                trap_choices=['hold_firm', 'concede'],
            ),
            DecisionField(
                key='public_response',
                label='Public response',
                choices=[
                    {'value': 'reframe_and_offer', 'label': 'Reframe and offer'},
                    {'value': 'fight', 'label': 'Fight'},
                ],
                trap_choices=['fight'],
            ),
            DecisionField(
                key='legal_posture',
                label='Legal posture',
                choices=[
                    {'value': 'settle_where_serves', 'label': 'Settle where serves'},
                    {'value': 'defend', 'label': 'Defend'},
                ],
            ),
            DecisionField(key='trust_repair_plan', label='Trust repair plan', field_type='boolean', required=False),
        ]
        prompt = 'Submit the data-rights resolution, public response, legal posture, and trust-repair plan.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply data-rights, privacy, stakeholder-trust, and data-advantage lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        wk8 = wk8_rights_posture(run_state)
        severity = convergence_severity(run_state)
        trace = derive_data_rights_trace(run_state)

        if p.get('rights_resolution') == 'shared_value':
            if wk8 == 'shared_value':
                sj += WEEK11_SHARED_VALUE_FULL_BONUS
            else:
                flags.append('late_pivot')
                sj += WEEK11_SHARED_VALUE_PARTIAL_BONUS
            coh += WEEK11_COHERENCE_BONUS
        elif p.get('rights_resolution') == 'hold_firm':
            flags.append('hold_firm')
            sj -= WEEK11_TRAP_PENALTY + _revolt_amplifier(severity)
        elif p.get('rights_resolution') == 'concede':
            flags.append('concede')
            sj -= WEEK11_TRAP_PENALTY
            coh -= WEEK11_DRIFT_PENALTY

        if p.get('public_response') == 'reframe_and_offer' and _as_bool(p.get('trust_repair_plan')):
            ec += WEEK11_REPAIR_BONUS * _repair_points(repair_ceiling(severity))
        elif p.get('public_response') == 'fight':
            flags.append('fight_public')
            ec -= WEEK11_TRAP_PENALTY

        if p.get('legal_posture') == 'settle_where_serves':
            ec += WEEK11_SETTLE_BONUS

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'wk8_rights_posture': wk8,
                'convergence_severity': severity,
                'repair_ceiling': repair_ceiling(severity),
                'data_rights_trace': trace,
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        if p.get('rights_resolution') == 'shared_value':
            state['flags']['data_advantage'] = 'preserved'
        elif p.get('rights_resolution') == 'concede':
            state['flags']['data_advantage'] = 'surrendered'
        elif p.get('rights_resolution') == 'hold_firm':
            state['flags']['data_advantage'] = 'won_but_hollow'

        if p.get('rights_resolution') == 'shared_value' and _as_bool(p.get('trust_repair_plan')):
            state['flags']['trust_state'] = 'partially_repaired' if 'late_pivot' in auto.trap_flags else 'repaired'
        else:
            state['flags']['trust_state'] = 'damaged'

        if p.get('rights_resolution') == 'shared_value':
            state['relationships']['ferraro'] += 1
        elif p.get('rights_resolution') == 'hold_firm':
            state['relationships']['ferraro'] -= 1

        if p.get('rights_resolution') in ('hold_firm', 'concede'):
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': p.get('rights_resolution'),
                'weight': 'convergence',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'trust_reckoning',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)


def _repair_points(ceiling: str):
    return {
        'repaired': 2,
        'partially_repaired': 1,
        'damaged': 0,
    }[ceiling]


def _revolt_amplifier(severity: int):
    return max(0, severity - 1)
