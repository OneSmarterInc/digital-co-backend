from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import derive_wk1_direction
from scoring.config import (
    WEEK4_COHERENCE_BONUS,
    WEEK4_DEEP_LOCKIN_INCREMENT,
    WEEK4_DRIFT_PENALTY,
    WEEK4_ENGINEERING_RESPECTED,
    WEEK4_ENGINEERING_SIDELINED,
    WEEK4_NEGOTIATION_BONUS,
    WEEK4_SOUND_SOURCING_BONUS,
    WEEK4_TOTAL_COST_TRUST,
    WEEK4_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week4Module(WeekModule):
    week_number = 4
    title = 'The Foundation'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'gates.budget_credibility',
            'through_lines.cloud_lockin',
            'flags.integrator_accelerator_taken',
            'relationships',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Separate what differentiates DigitalCo from commodity platform plumbing.',
                'Upfront credits are not the same thing as lifetime cost.',
                'The sourcing decision also tells Fischer whether engineering is a partner.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'With S/4 triage behind them, the CIO turns to the platform that must carry '
                'connected-products and the data-services strategy: telemetry ingestion, analytics, '
                'and the services layer. A major cloud provider arrives with credits, free migration '
                'help, dedicated engineers, and a multi-year rate that looks like relief after the '
                'migration crisis. Reinhardt sees attractive upfront economics, Chen wants visible '
                'movement, and the budget depends on what the team preserved in Week 3.'
            ),
            exec_reads=[
                'Reinhardt: drawn to the sweet deal unless the team argues lifetime cost.',
                'Chen: wants the data bet moving, with less patience for sourcing nuance.',
                'Fischer: watches whether engineering is respected as co-builder or sidelined.',
                'Calloway and the board: watching the last Phase 1 decision before the first benchmark.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        sweet_note = ''
        if tier == Tier.UNDERGRAD:
            sweet_note = ' The cheap entry price carries switching cost once fleet data accumulates.'
        return [
            Artifact(
                title='Three Sourcing Paths',
                body=(
                    'In-house build creates capability slowly and expensively; packaged vendor '
                    'platforms provide capability with license limits; hyperscaler managed services '
                    'stand up fastest and cheapest at entry.'
                ),
            ),
            Artifact(
                title='Core-versus-Context Analysis',
                body=(
                    'The differentiating layer is the proprietary data-and-services capability. '
                    'Compute, storage, and basic ingestion are commodity plumbing.'
                ),
            ),
            Artifact(
                title='Cloud Deal Terms',
                body=(
                    'The credits and free migration assistance make the upfront number small. '
                    'The lifetime profile depends on data gravity, egress, scale, proprietary '
                    'services, and the practical cost of walking away after fleet telemetry grows.'
                    + sweet_note
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        budget_state = run_state['gates']['budget_credibility']['state']
        depth = run_state['through_lines']['cloud_lockin']['depth']
        contexts = {
            'marcus_webb': WeekAdvisorContext(
                facts=['Core-versus-context is the central sourcing logic.', f'Existing lock-in depth: {depth}'],
                stance='Own what differentiates; rent what is commodity.',
                signal='Do not build everything just because architecture is interesting.',
                misdirection='Architect pride can overbuild commodity plumbing.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=[
                    'The credits and migration assistance are the bait.',
                    f'Budget credibility gate: {budget_state}',
                ],
                stance='Ask what it costs to leave in three years, not just what it costs to join today.',
                signal='Negotiate portability and exit terms instead of swallowing the offer whole.',
                misdirection='Do not reveal future week consequences.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Derived Week 1 direction: {derive_wk1_direction(run_state)}'],
                stance='Protect the differentiating layer of the data-services strategy.',
                signal='The platform should equip the strategy, not starve it.',
                misdirection='Do not over-invest in every layer.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['The sourcing decision must match the Week 2 alignment.', 'Fischer politics matter.'],
                stance='Connect the platform decision to the story the team already told the board.',
                signal='How the team frames engineering partnership matters.',
                misdirection='Do not make this purely a cloud economics discussion.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['Fleet and OT data will flow into this platform.', 'Factory-floor exposure remains unresolved.'],
                stance='Keep security posture visible while sourcing the platform.',
                signal='New front doors require control discipline.',
                misdirection='Do not invent a breach or future crisis.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['Platform choice shapes the services teams can imagine and launch.'],
                stance='Keep future-state imagination tied to build-buy-rent realism.',
                signal='The platform is foundation, not the product itself.',
                misdirection='Do not sell hype as capability.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Budget credibility gate: {budget_state}', f'Existing lock-in depth: {depth}'],
            stance='Help the team choose a sourcing strategy without spoiling hidden future consequences.',
            signal='Lifetime cost matters more than entry price.',
            misdirection='Do not reveal future week consequences.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(
                key='sourcing_rationale',
                label='Sourcing strategy and cloud commitment rationale',
                field_type='textarea',
            ),
            DecisionField(
                key='sourcing_approach',
                label='Sourcing approach',
                choices=[
                    {'value': 'core_context_split', 'label': 'Core/context split'},
                    {'value': 'build_everything', 'label': 'Build everything'},
                    {'value': 'rent_cheapest', 'label': 'Rent cheapest'},
                ],
                trap_choices=['build_everything'],
            ),
            DecisionField(
                key='differentiator_layer',
                label='Differentiator layer',
                choices=[
                    {'value': 'own', 'label': 'Own'},
                    {'value': 'rent', 'label': 'Rent'},
                ],
                trap_choices=['rent'],
            ),
            DecisionField(
                key='cloud_commitment',
                label='Cloud commitment',
                choices=[
                    {'value': 'portability_protected', 'label': 'Portability protected'},
                    {'value': 'sweet_deal_as_written', 'label': 'Sweet deal as written'},
                    {'value': 'multi_vendor', 'label': 'Multi-vendor'},
                ],
                trap_choices=['sweet_deal_as_written'],
            ),
        ]
        prompt = 'Submit the platform sourcing strategy, differentiator ownership, and cloud commitment terms.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply TCO, core-versus-context, and build-buy-rent lenses.'
        return DecisionSpec(
            fields=fields,
            deliverable_prompt=prompt,
            rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate',
        )

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0

        if p.get('cloud_commitment') == 'sweet_deal_as_written':
            flags.append('sweet_deal_lockin')
            sj -= WEEK4_TRAP_PENALTY
        if p.get('sourcing_approach') == 'build_everything':
            flags.append('build_everything')
            sj -= WEEK4_TRAP_PENALTY
        if p.get('sourcing_approach') == 'core_context_split' and p.get('cloud_commitment') == 'portability_protected':
            sj += WEEK4_SOUND_SOURCING_BONUS

        if p.get('cloud_commitment') == 'portability_protected':
            ec += WEEK4_NEGOTIATION_BONUS

        wk1_direction = derive_wk1_direction(run_state)
        if wk1_direction == 'data_services' and p.get('differentiator_layer') == 'rent':
            coh -= WEEK4_DRIFT_PENALTY
            flags.append('starved_differentiator')
        elif p.get('differentiator_layer') == 'own':
            coh += WEEK4_COHERENCE_BONUS

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'sourcing_approach': p.get('sourcing_approach'),
                'differentiator_layer': p.get('differentiator_layer'),
                'cloud_commitment': p.get('cloud_commitment'),
                'wk1_direction': wk1_direction,
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        cloud = state['through_lines']['cloud_lockin']

        if p.get('cloud_commitment') == 'sweet_deal_as_written':
            cloud['state'] = 'locked'
            cloud['depth'] += WEEK4_DEEP_LOCKIN_INCREMENT
            cloud['notes'].append(
                'Sweet hyperscaler deal taken as written in Week 4 - detonates Weeks 7 and 12'
            )
        elif p.get('cloud_commitment') in ('portability_protected', 'multi_vendor'):
            cloud['notes'].append('Cloud commitment structured with portability or optionality in Week 4')

        if p.get('sourcing_approach') == 'core_context_split' and p.get('differentiator_layer') == 'own':
            state['relationships']['fischer'] += WEEK4_ENGINEERING_RESPECTED
        elif p.get('sourcing_approach') == 'rent_cheapest':
            state['relationships']['fischer'] -= WEEK4_ENGINEERING_SIDELINED

        if p.get('cloud_commitment') == 'portability_protected' and p.get('sourcing_approach') == 'core_context_split':
            state['relationships']['reinhardt'] += WEEK4_TOTAL_COST_TRUST
        elif 'sweet_deal_lockin' in auto.trap_flags:
            state['relationships']['reinhardt'] -= 1

        if 'starved_differentiator' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'starved_differentiator',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'platform_sourcing',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state
