from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import squeeze_severity, wk4_took_sweet_deal
from scoring.config import (
    WEEK12_COHERENCE_BONUS,
    WEEK12_COMMITTED_SPEND_INCREMENT,
    WEEK12_COST_CURVE_BONUS,
    WEEK12_DRIFT_PENALTY,
    WEEK12_FINOPS_BONUS,
    WEEK12_RENEGOTIATE_STRENGTH_BONUS,
    WEEK12_RENEGOTIATE_WEAK_BONUS,
    WEEK12_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week12Module(WeekModule):
    week_number = 12
    title = 'The Reckoning of Cost'

    def reads_state(self) -> list[str]:
        return [
            'through_lines.cloud_lockin',
            'flags.hedge_begun',
            'decision_history',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'gates.budget_credibility',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'The committed-spend discount rhymes with the Week 4 sweet deal.',
                'The durable fix is architectural: edge processing, selective repatriation, and FinOps.',
                'Renegotiation is stronger if the team began hedging in Week 7.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The cloud bill is now one of the largest and fastest-growing lines in the IT budget. '
                'Fleet telemetry, storage, egress, compute, and the AI workloads added in Week 9 '
                'scale with the success of the data-services strategy. The hyperscaler offers relief: '
                'a committed-spend discount that lowers the bill now in exchange for a deeper '
                'multi-year cage. The task is to make the infrastructure economics sustainable, break '
                'the data-gravity curve, and decide whether DigitalCo learned from the lock-in pattern '
                'it has already lived through.'
            ),
            exec_reads=[
                'Reinhardt: drawn to the discount because the bill is real.',
                'Chen: wants the data-services bet to stand on its own economics.',
                'Calloway: watches whether the CIO manages consequences or defers them again.',
                'The board: reads cost sustainability as proof the strategy can scale.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Cloud Bill Detail',
                body=(
                    'Storage, egress, compute, and AI workloads are growing faster than the fleet. '
                    'Telemetry accumulates in the cloud instead of being filtered near the source.'
                ),
            ),
            Artifact(
                title='Week 4 Terms and Week 7 Hedge',
                body=(
                    'Teams with portability and a hedge have leverage. Teams that took the sweet deal '
                    'and never hedged are negotiating from inside the cost curve.'
                ),
            ),
            Artifact(
                title='Committed-Spend Offer',
                body=(
                    'The hyperscaler offers lower rates for a larger multi-year commitment. It lowers '
                    'today\'s bill while deepening the dependency.'
                ),
            ),
            Artifact(
                title='Edge and Repatriation Architecture',
                body=(
                    'Process more telemetry at the machine and customer site, repatriate workloads '
                    'where cloud economics fail, and use FinOps discipline for what remains.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        severity = squeeze_severity(run_state)
        took_sweet = wk4_took_sweet_deal(run_state)
        hedged = run_state.get('flags', {}).get('hedge_begun', False)
        contexts = {
            'frank_delgado': WeekAdvisorContext(
                facts=[f'Week 4 sweet deal taken: {took_sweet}', f'Hedge begun: {hedged}'],
                stance='Name the committed-spend discount as the same trap wearing new clothes.',
                signal='The question is whether the organization learned from Week 4.',
                misdirection='Do not make every discount look automatically bad; make the cage visible.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=[f'Cloud squeeze severity: {severity}'],
                stance='Show the architecture that breaks the cost curve.',
                signal='Edge processing and selective repatriation address data gravity at the source.',
                misdirection='Do not pretend negotiation alone fixes architecture.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=[f'Week 4 sweet deal taken: {took_sweet}'],
                stance='Frame Week 12 as a learning-across-the-arc test.',
                signal='A repeated mistake is a coherence failure, not only a cost mistake.',
                misdirection='Do not let a good memo hide a repeated pattern.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=['The data-services bet still needs sustainable infrastructure.'],
                stance='Protect the strategy while changing the economics underneath it.',
                signal='The edge fix serves the strategy; it does not retreat from it.',
                misdirection='Do not break the data-services bet to lower the bill.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['Edge and repatriated workloads introduce their own control surfaces.'],
                stance='Keep the infrastructure fix securable.',
                signal='Architecture repair must include security design.',
                misdirection='Do not turn this back into a breach week.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Cloud squeeze severity: {severity}', f'Hedge begun: {hedged}'],
            stance='Help the team make the infrastructure economics sustainable.',
            signal='The learning test is whether the team repeats the lock-in pattern.',
            misdirection='Do not reveal Week 14 synthesis.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='cost_reckoning_rationale', label='Infrastructure cost and lock-in rationale', field_type='textarea'),
            DecisionField(
                key='architecture',
                label='Infrastructure architecture',
                choices=[
                    {'value': 'edge_and_repatriate', 'label': 'Edge and repatriate'},
                    {'value': 'centralize', 'label': 'Centralize'},
                    {'value': 'minimal_change', 'label': 'Minimal change'},
                ],
                trap_choices=['centralize', 'minimal_change'],
            ),
            DecisionField(
                key='hyperscaler_decision',
                label='Hyperscaler decision',
                choices=[
                    {'value': 'committed_spend_discount', 'label': 'Committed-spend discount'},
                    {'value': 'renegotiate', 'label': 'Renegotiate'},
                    {'value': 'hedge_further', 'label': 'Hedge further'},
                ],
                trap_choices=['committed_spend_discount'],
            ),
            DecisionField(key='finops_discipline', label='FinOps discipline', field_type='boolean', required=False),
        ]
        prompt = 'Submit the infrastructure architecture, hyperscaler decision, and cost-governance discipline.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply cloud economics, data gravity, edge/repatriation, and FinOps lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        hedged = run_state.get('flags', {}).get('hedge_begun', False)
        took_sweet_deal = wk4_took_sweet_deal(run_state)

        if p.get('architecture') == 'edge_and_repatriate':
            sj += WEEK12_COST_CURVE_BONUS
        elif p.get('architecture') == 'centralize':
            flags.append('data_gravity')
            sj -= WEEK12_TRAP_PENALTY
        elif p.get('architecture') == 'minimal_change':
            flags.append('stayed_trapped')
            sj -= WEEK12_TRAP_PENALTY

        if p.get('hyperscaler_decision') == 'committed_spend_discount':
            flags.append('committed_spend_retrap')
            sj -= WEEK12_TRAP_PENALTY
        elif p.get('hyperscaler_decision') == 'renegotiate':
            ec += WEEK12_RENEGOTIATE_STRENGTH_BONUS if hedged else WEEK12_RENEGOTIATE_WEAK_BONUS

        if _as_bool(p.get('finops_discipline')):
            ec += WEEK12_FINOPS_BONUS

        if p.get('hyperscaler_decision') == 'committed_spend_discount':
            coh -= WEEK12_DRIFT_PENALTY
            if took_sweet_deal:
                flags.append('did_not_learn')
                coh -= WEEK12_DRIFT_PENALTY
        elif p.get('architecture') == 'edge_and_repatriate':
            coh += WEEK12_COHERENCE_BONUS
            if took_sweet_deal:
                flags.append('learned')

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'squeeze_severity': squeeze_severity(run_state),
                'hedge_begun': hedged,
                'wk4_took_sweet_deal': took_sweet_deal,
                'architecture': p.get('architecture'),
                'hyperscaler_decision': p.get('hyperscaler_decision'),
                'finops_discipline': _as_bool(p.get('finops_discipline')),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        cloud = state['through_lines']['cloud_lockin']

        state['flags']['infra_sustainable'] = p.get('architecture') == 'edge_and_repatriate'

        if 'learned' in auto.trap_flags:
            state['flags']['lockin_lesson'] = 'learned'
        elif 'did_not_learn' in auto.trap_flags:
            state['flags']['lockin_lesson'] = 'not_learned'

        if p.get('hyperscaler_decision') == 'committed_spend_discount':
            cloud['depth'] += WEEK12_COMMITTED_SPEND_INCREMENT
            cloud['notes'].append('Committed-spend discount taken in Week 12 - the cage deepened again')
        elif p.get('architecture') == 'edge_and_repatriate':
            cloud['state'] = 'broken'
            cloud['notes'].append('Cost curve broken with edge architecture in Week 12')

        if p.get('architecture') == 'edge_and_repatriate':
            state['relationships']['reinhardt'] += 1
        elif 'committed_spend_retrap' in auto.trap_flags:
            state['relationships']['reinhardt'] -= 1

        if 'data_gravity' in auto.trap_flags or 'committed_spend_retrap' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'lockin_unbroken',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'cost_reckoning',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)
