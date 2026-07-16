from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from scoring.config import (
    WEEK9_AI_CONCENTRATION_INCREMENT,
    WEEK9_COHERENCE_BONUS,
    WEEK9_DEEP_VALUE_BONUS,
    WEEK9_DRIFT_PENALTY,
    WEEK9_GOVERNANCE_BONUS,
    WEEK9_GOVERNANCE_WEAK_BONUS,
    WEEK9_TRAP_PENALTY,
    WEEK9_WEAK_VALUE_BONUS,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week9Module(WeekModule):
    week_number = 9
    title = 'The Bet'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'flags.predictive_built',
            'flags.governance_built',
            'through_lines.cloud_lockin',
            'gates.security_ot',
            'gates.budget_credibility',
            'relationships',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'The board is right to want AI; the trap is giving it theater instead of substance.',
                'Predictive maintenance compounds the Week 8 data foundation.',
                'Shadow AI needs governance before the incident becomes the story.',
                'Concentrating AI on the same hyperscaler repeats the lock-in lesson.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The board wants an AI strategy, and this time the instinct is sound. DigitalCo '
                'should be able to turn proprietary fleet telemetry into a durable AI advantage. '
                'The pressure is not to resist AI; it is to give the board something real rather '
                'than a demo. Predictive maintenance on the connected fleet is the deep play if '
                'the Week 8 data foundation exists. Meanwhile, shadow AI is already running in '
                'engineering, dealers, and marketing, carrying IP, liability, and governance risk.'
            ),
            exec_reads=[
                'Chen and Whitfield: want AI and are correct, but their picture of AI is fuzzy.',
                'Reinhardt: wants return, not another visible program without payoff.',
                'Fischer: her engineers are heavy shadow-AI users and need a real regime.',
                'Ferraro: dealers are already experimenting with customer-facing chatbots.',
                'Calloway: watches whether the AI bet strengthens the board story or hollows it out.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='AI Opportunity Landscape',
                body=(
                    'Predictive maintenance on proprietary fleet telemetry creates defensible value. '
                    'Computer vision and selected dealer/parts agents can be real but narrower. '
                    'A broad scatter of copilots and chatbots produces visible activity without '
                    'compounding advantage.'
                ),
            ),
            Artifact(
                title='Shadow-AI Incident',
                body=(
                    'Engineers are pasting design work into public models and dealers are testing '
                    'chatbots without a common policy. The incident is a governance test, not a '
                    'reason to abandon AI.'
                ),
            ),
            Artifact(
                title='Build Versus Rent',
                body=(
                    'Foundation models are commodity context; models and workflows trained on '
                    'DigitalCo fleet telemetry are differentiating. The Week 4 core-versus-context '
                    'logic applies again.'
                ),
            ),
            Artifact(
                title='Vendor Concentration',
                body=(
                    'Putting the AI stack on the same hyperscaler that created the squeeze deepens '
                    'the dependence the team just learned to hedge.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        predictive = run_state.get('flags', {}).get('predictive_built', False)
        governance = run_state.get('flags', {}).get('governance_built', False)
        contexts = {
            'daniel_stern': WeekAdvisorContext(
                facts=['The board wants AI and the strategic instinct is sound.', f'Predictive foundation built: {predictive}'],
                stance='Make the bold AI case while separating value from theater.',
                signal='The right board-aligned move is real AI value, not demos everywhere.',
                misdirection='Do not treat board enthusiasm as automatically wrong this week.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['There are many visible AI use cases.', 'Novelty can look like momentum.'],
                stance='Bring frontier imagination but avoid breadth-for-show.',
                signal='Choose use cases that compound proprietary data advantage.',
                misdirection='Do not mistake a portfolio of demos for a business.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=[f'Predictive foundation built: {predictive}'],
                stance='Separate a chatbot demo from an operating advantage.',
                signal='Predictive maintenance is valuable only if the Week 8 data foundation exists.',
                misdirection='Do not promise predictive value on a data swamp.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['Shadow AI is already leaking into engineering and channel workflows.'],
                stance='Make the incident governable before it becomes larger.',
                signal='Governance enables AI; it is not anti-AI drag.',
                misdirection='Do not turn the week into a blanket AI ban.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=[f'Cloud lock-in depth: {run_state["through_lines"]["cloud_lockin"]["depth"]}'],
                stance='Ask whether the AI sourcing repeats the same hyperscaler dependency.',
                signal='Own differentiating models and hedge commodity AI vendors.',
                misdirection='Do not make every rented model look wrong.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['This is the release-valve week: the board is right to want substance.'],
                stance='Translate board demand into return-producing AI.',
                signal='Theater fails the board by seeming to satisfy it.',
                misdirection='Do not apply the usual board-pleasing-is-trap reflex.',
            ),
            'gloria_tran': WeekAdvisorContext(
                facts=['Dealer chatbots and public-model uploads create liability and IP exposure.'],
                stance='Turn shadow AI into governed AI.',
                signal='A plan matters before the next bad answer or leaked design.',
                misdirection='Do not make legal risk an excuse for no AI.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Predictive foundation built: {predictive}', f'Governance built: {governance}'],
            stance='Help the team turn board AI demand into real value.',
            signal='Substance scores here; theater does not.',
            misdirection='Do not reveal later shadow-AI consequences.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='ai_strategy_rationale', label='AI strategy rationale', field_type='textarea'),
            DecisionField(
                key='deployment',
                label='Deployment strategy',
                choices=[
                    {'value': 'predictive_maintenance_core', 'label': 'Predictive maintenance core'},
                    {'value': 'narrow_real', 'label': 'Narrow real use cases'},
                    {'value': 'theater_scatter', 'label': 'Theater scatter'},
                ],
                trap_choices=['theater_scatter'],
            ),
            DecisionField(
                key='ai_sourcing',
                label='AI sourcing',
                choices=[
                    {'value': 'build_differentiating_rent_commodity', 'label': 'Build differentiating, rent commodity'},
                    {'value': 'rent_everything', 'label': 'Rent everything'},
                    {'value': 'build_everything', 'label': 'Build everything'},
                ],
            ),
            DecisionField(
                key='vendor_concentration',
                label='Vendor concentration',
                choices=[
                    {'value': 'hedged', 'label': 'Hedged'},
                    {'value': 'single_hyperscaler', 'label': 'Single hyperscaler'},
                ],
                trap_choices=['single_hyperscaler'],
            ),
            DecisionField(
                key='shadow_ai_response',
                label='Shadow-AI response',
                choices=[
                    {'value': 'governed_with_plan', 'label': 'Governed with plan'},
                    {'value': 'ungoverned', 'label': 'Ungoverned'},
                ],
                trap_choices=['ungoverned'],
            ),
        ]
        prompt = 'Submit the AI deployment, sourcing, vendor, and shadow-AI governance strategy.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply AI value-chain, build-versus-rent, governance, and lock-in lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        foundation = run_state.get('flags', {}).get('predictive_built', False)

        if p.get('deployment') == 'predictive_maintenance_core':
            if foundation:
                sj += WEEK9_DEEP_VALUE_BONUS
            else:
                flags.append('no_foundation')
                sj += WEEK9_WEAK_VALUE_BONUS
        elif p.get('deployment') == 'theater_scatter':
            flags.append('ai_theater')
            sj -= WEEK9_TRAP_PENALTY

        if p.get('vendor_concentration') == 'single_hyperscaler':
            flags.append('lockin_unlearned')
            sj -= WEEK9_TRAP_PENALTY

        if p.get('shadow_ai_response') == 'ungoverned':
            flags.append('ungoverned_shadow_ai')
            ec -= WEEK9_TRAP_PENALTY
        elif p.get('shadow_ai_response') == 'governed_with_plan':
            ec += WEEK9_GOVERNANCE_BONUS if run_state.get('flags', {}).get('governance_built') else WEEK9_GOVERNANCE_WEAK_BONUS

        if p.get('deployment') == 'theater_scatter':
            coh -= WEEK9_DRIFT_PENALTY
        elif p.get('deployment') == 'predictive_maintenance_core' and foundation:
            coh += WEEK9_COHERENCE_BONUS

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'deployment': p.get('deployment'),
                'ai_sourcing': p.get('ai_sourcing'),
                'vendor_concentration': p.get('vendor_concentration'),
                'shadow_ai_response': p.get('shadow_ai_response'),
                'predictive_built': foundation,
                'governance_built': run_state.get('flags', {}).get('governance_built', False),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        if p.get('shadow_ai_response') == 'governed_with_plan':
            state['flags']['shadow_ai_governed'] = True
        else:
            state['flags']['shadow_ai_incident_open'] = True
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'shadow_ai_ungoverned',
            })

        if p.get('vendor_concentration') == 'single_hyperscaler':
            state['through_lines']['cloud_lockin']['depth'] += WEEK9_AI_CONCENTRATION_INCREMENT
            state['through_lines']['cloud_lockin']['notes'].append(
                'AI concentrated on the same hyperscaler in Week 9 - deepens the later lock-in reckoning'
            )

        if p.get('deployment') == 'predictive_maintenance_core' and state.get('flags', {}).get('predictive_built'):
            state['relationships']['reinhardt'] += 1
        if p.get('shadow_ai_response') == 'governed_with_plan':
            state['relationships']['fischer'] += 1
            state['relationships']['tran'] += 1

        if 'ai_theater' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'ai_theater',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'ai_bet',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state
