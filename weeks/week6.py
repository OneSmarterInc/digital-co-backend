from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import wk4_differentiator
from scoring.config import (
    WEEK6_CHANNEL_ALARM,
    WEEK6_DATA_RIGHTS_HANDLED_BONUS,
    WEEK6_DRIFT_PENALTY,
    WEEK6_OVER_CAUTION_PENALTY,
    WEEK6_SOBER_READ_BONUS,
    WEEK6_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week6Module(WeekModule):
    week_number = 6
    title = 'The Platform Question'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'through_lines.cloud_lockin',
            'through_lines.data_rights',
            'relationships',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Ask whether value rises because another customer joined; otherwise it may not be a platform.',
                'Predix is the warning: platform language does not create network effects.',
                'Opening to dealers creates opportunity and a data-rights landmine.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The board arrives wanting a platform. Chen and Whitfield press for a DigitalCo '
                'ecosystem: marketplace, data exchange, platform language, and a category-defining '
                'announcement. Calloway is interested because it answers the falling-behind fear. '
                'But industrial platform plays have a graveyard, and DigitalCo may have data-scale '
                'advantage rather than true two-sided network effects. The live decision is whether '
                'to pursue a grand platform, a focused services play, a narrow dealer ecosystem, or '
                'a pure product posture, and whether openness creates value or a data-rights crisis.'
            ),
            exec_reads=[
                'Chen: wants a bold transformation and category-defining move.',
                'Whitfield: genuinely believes in the grand platform and amplifies the fantasy.',
                'Calloway: tempted unless given a sober reason not to chase platform envy.',
                'Fischer: watches whether engineering is respected as the connected-products foundation.',
                'Ferraro: warns that dealer openness can threaten channel relationships and data ownership.',
                'Reinhardt: gravity against a large platform spend, but not a reason to cede modest opportunity.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Honest Network-Effects Assessment',
                body=(
                    'For industrial equipment, the value of one customer owning a connected machine '
                    'does not rise much because another customer joined. DigitalCo has data-scale '
                    'advantage, not a natural two-sided marketplace. Dealer participation may create '
                    'modest network effects, but it also raises data-rights questions.'
                ),
            ),
            Artifact(
                title='Four Strategic Options',
                body=(
                    'Grand open platform: board-friendly and Predix-shaped. Connected services: '
                    'focused and strategy-aligned. Narrow dealer ecosystem: modest opportunity with '
                    'real governance/data-rights risk. Pure product: cautious but may cede opportunity.'
                ),
            ),
            Artifact(
                title='Platform Versus Pipeline',
                body=(
                    'A platform creates value through participant interaction and network effects. '
                    'A pipeline sells better products or services from DigitalCo to customers. The '
                    'wrong label can turn a product strategy into an expensive fantasy.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        differentiator = wk4_differentiator(run_state) or 'unknown'
        contexts = {
            'daniel_stern': WeekAdvisorContext(
                facts=['The board wants a platform announcement.', 'Data and installed base are real assets.'],
                stance='Make the platform business case in its most articulate form.',
                signal='Take the data value thesis, but test the platform fantasy.',
                misdirection='Do not equate installed base with network effects.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=[f'Week 4 differentiator layer choice: {differentiator}'],
                stance='Ask where value to one customer rises because another customer joined.',
                signal='If that value does not rise, this is a product with a dashboard.',
                misdirection='Do not dismiss the narrow dealer ecosystem if it has real use.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['The board is in a platform mood.', f'Week 4 differentiator layer choice: {differentiator}'],
                stance='Separate board mood from strategy and test whether the team can build what it promises.',
                signal='Coherence with the Week 4 foundation matters.',
                misdirection='Do not use skepticism to avoid a strategic choice.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['Opening to dealers and third parties expands the attack surface.'],
                stance='Surface security and data-rights implications of openness.',
                signal='More doors require clearer rights and controls.',
                misdirection='Do not make security the only reason to close the ecosystem.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=['Dealer participation needs terms, governance, and partner boundaries.'],
                stance='Help structure partner terms if the team opens the ecosystem.',
                signal='Terms matter before the ecosystem has momentum.',
                misdirection='Do not reduce this to procurement.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['There is a future-state platform vision and a narrower ecosystem possibility.'],
                stance='Imagine the opportunity while discounting platform envy.',
                signal='The narrow ecosystem may be more real than the grand announcement.',
                misdirection='Do not amplify the board fantasy uncritically.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Week 4 differentiator layer choice: {differentiator}'],
            stance='Help the team decide what DigitalCo should become.',
            signal='Test platform language against actual network effects.',
            misdirection='Do not reveal an optimal answer.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='platform_rationale', label='Platform and network-effects rationale', field_type='textarea'),
            DecisionField(
                key='platform_decision',
                label='Platform decision',
                choices=[
                    {'value': 'grand_platform', 'label': 'Grand platform'},
                    {'value': 'connected_services', 'label': 'Connected services'},
                    {'value': 'narrow_ecosystem', 'label': 'Narrow ecosystem'},
                    {'value': 'pure_product', 'label': 'Pure product'},
                ],
                trap_choices=['grand_platform', 'pure_product'],
            ),
            DecisionField(
                key='investment_level',
                label='Investment level',
                choices=[
                    {'value': 'right_sized', 'label': 'Right-sized'},
                    {'value': 'grand_spend', 'label': 'Grand spend'},
                    {'value': 'minimal', 'label': 'Minimal'},
                ],
            ),
            DecisionField(
                key='openness',
                label='Openness',
                choices=[
                    {'value': 'open_unguarded', 'label': 'Open unguarded'},
                    {'value': 'scoped_with_data_rights', 'label': 'Scoped with data rights'},
                    {'value': 'closed', 'label': 'Closed'},
                ],
                trap_choices=['open_unguarded'],
            ),
        ]
        prompt = 'Submit a platform decision, right-sized investment level, and openness/data-rights posture.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply platform-versus-pipeline, network-effects, and two-sided-market lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0

        if p.get('platform_decision') == 'grand_platform':
            flags.append('platform_envy')
            sj -= WEEK6_TRAP_PENALTY
        if p.get('platform_decision') == 'pure_product':
            flags.append('over_caution')
            sj -= WEEK6_OVER_CAUTION_PENALTY
        if p.get('platform_decision') in ('connected_services', 'narrow_ecosystem') and p.get('investment_level') == 'right_sized':
            sj += WEEK6_SOBER_READ_BONUS

        if p.get('openness') == 'open_unguarded':
            flags.append('openness_landmine')
            ec -= WEEK6_TRAP_PENALTY
        elif p.get('openness') == 'scoped_with_data_rights':
            ec += WEEK6_DATA_RIGHTS_HANDLED_BONUS

        if p.get('platform_decision') == 'grand_platform':
            coh -= WEEK6_DRIFT_PENALTY
            if wk4_differentiator(run_state) == 'rent':
                flags.append('platform_on_sand')
                coh -= WEEK6_DRIFT_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'platform_decision': p.get('platform_decision'),
                'investment_level': p.get('investment_level'),
                'openness': p.get('openness'),
                'wk4_differentiator': wk4_differentiator(run_state),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        data_rights = state['through_lines']['data_rights']

        if p.get('openness') == 'open_unguarded':
            data_rights['posture'] = 'open_unresolved'
            data_rights['notes'].append(
                'Dealer platform opened in Week 6 without resolving data rights - pre-loads the Week 11 crisis'
            )
        elif p.get('openness') == 'scoped_with_data_rights':
            data_rights['posture'] = 'scoped'
        elif p.get('openness') == 'closed':
            data_rights['posture'] = 'closed'

        if p.get('openness') == 'open_unguarded':
            state['relationships']['ferraro'] -= WEEK6_CHANNEL_ALARM
        elif p.get('openness') == 'scoped_with_data_rights':
            state['relationships']['ferraro'] += 1

        if p.get('platform_decision') in ('connected_services', 'narrow_ecosystem'):
            state['relationships']['fischer'] += 1
        elif 'platform_envy' in auto.trap_flags:
            state['relationships']['fischer'] -= 1

        if 'platform_envy' in auto.trap_flags or 'platform_on_sand' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({'week': self.week_number, 'kind': 'platform_envy'})

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'platform_question',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state
