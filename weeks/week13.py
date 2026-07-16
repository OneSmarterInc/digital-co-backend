from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.climax import arc_coherence, board_receptiveness
from scoring.config import WEEK13_AUDIT_COHERENCE, WEEK13_PARTIAL_PENALTY, WEEK13_TRAP_PENALTY

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week13Module(WeekModule):
    week_number = 13
    title = 'The Audit'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'relationships',
            'gates',
            'flags',
            'benchmarks.latest',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'The board evaluates the whole record, not just the deck.',
                'Frame the transformation as the legacy extended, not betrayed.',
                'Use board language: risk, return, ask, credibility.',
                'Prepare for the hostile premise question.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The board convenes to judge whether DigitalCo has earned another major commitment. '
                'The CIO must present the data-and-services transformation, the business case, and '
                'the ask for funding and mandate. But the room has a memory. Crises handled or '
                'botched, relationships built or burned, trust repaired or damaged, and coherence '
                'kept or lost all arrive before the first slide. The presentation meets the board '
                'state the organization has created.'
            ),
            exec_reads=[
                'Ashby: respect is winnable if the legacy is extended rather than betrayed.',
                'Sokolski: will attack the premise that DigitalCo should transform at all.',
                'Chen: wants the bet and demands real numbers.',
                'Whitfield: champions the digital case but can over-set expectations.',
                'Hargrove: the swing vote whose confidence tracks the accumulated record.',
                'Calloway: carries the pitch only if the team gave him cover and delivered.',
                'Reinhardt: ally or challenger depending on financial credibility earned across the arc.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='The Accumulated Arc',
                body=(
                    'The Week 1 thesis, platform choices, data strategy, AI bet, breach handling, '
                    'data-rights repair, and infrastructure reckoning must form one story.'
                ),
            ),
            Artifact(
                title='Board State',
                body=(
                    'The board factions are known, but receptiveness is produced by accumulated '
                    'relationships, gates, trust, advantage, execution, and coherence.'
                ),
            ),
            Artifact(
                title='Business Case and Ask',
                body=(
                    'Translate the strategy into risk, return, investment, mandate, and go decision. '
                    'An ask too small concedes the prize; an ask too large cannot be granted.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        arc = _arc(run_state)
        receptiveness = board_receptiveness(run_state)
        contexts = {
            'diane_brandt': WeekAdvisorContext(
                facts=[f'Arc coherence: {arc}', f'Board receptiveness: {receptiveness}'],
                stance='Make the team tell the story its record actually supports.',
                signal='The meeting reveals the arc; it does not rescue it.',
                misdirection='Do not let deck polish cover contradictions.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Data advantage: {run_state.get("flags", {}).get("data_advantage")}'],
                stance='Shape the business case in board language.',
                signal='The data advantage is the thesis; the ask must match the return.',
                misdirection='Do not turn this into architecture theater.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['The board cares what the architecture does and costs.'],
                stance='Translate technical reality into business outcomes.',
                signal='Show capability, economics, and risk reduction instead of diagrams.',
                misdirection='Do not over-explain implementation details.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Arc coherence: {arc}', f'Board receptiveness: {receptiveness}'],
            stance='Help the team present the accumulated strategy honestly.',
            signal='The board remembers the record.',
            misdirection='Do not invent a better history than the state supports.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='audit_rationale', label='Board audit rationale', field_type='textarea'),
            DecisionField(
                key='narrative_coherence',
                label='Narrative coherence',
                choices=[
                    {'value': 'coherent', 'label': 'Coherent'},
                    {'value': 'partial', 'label': 'Partial'},
                    {'value': 'contradictory', 'label': 'Contradictory'},
                ],
                trap_choices=['contradictory'],
            ),
            DecisionField(
                key='business_case',
                label='Business case',
                choices=[
                    {'value': 'board_language', 'label': 'Board language'},
                    {'value': 'technical_jargon', 'label': 'Technical jargon'},
                ],
                trap_choices=['technical_jargon'],
            ),
            DecisionField(
                key='ask_sizing',
                label='Ask sizing',
                choices=[
                    {'value': 'well_sized', 'label': 'Well sized'},
                    {'value': 'too_big', 'label': 'Too big'},
                    {'value': 'too_small', 'label': 'Too small'},
                ],
                trap_choices=['too_big', 'too_small'],
            ),
            DecisionField(
                key='hostile_question_handled',
                label='Hostile question handled',
                choices=[
                    {'value': 'defended', 'label': 'Defended'},
                    {'value': 'folded', 'label': 'Folded'},
                ],
                trap_choices=['folded'],
            ),
        ]
        prompt = 'Submit the board narrative, business case, ask, and hostile-question defense.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply board communication, business-case, and strategic-narrative lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        arc = _arc(run_state)
        coh = WEEK13_AUDIT_COHERENCE[arc]

        if arc == 'weak':
            flags.append('incoherence_reckoning')
        if p.get('narrative_coherence') == 'contradictory':
            flags.append('contradictory_deck')

        if p.get('ask_sizing') in ('too_big', 'too_small'):
            flags.append('mis_sized_ask')
            sj -= WEEK13_TRAP_PENALTY
        if p.get('hostile_question_handled') == 'folded':
            flags.append('folded')
            sj -= WEEK13_TRAP_PENALTY
            ec -= WEEK13_PARTIAL_PENALTY
        if p.get('business_case') == 'technical_jargon':
            flags.append('jargon')
            ec -= WEEK13_PARTIAL_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'arc_coherence': arc,
                'board_receptiveness': board_receptiveness(run_state),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        receptiveness = board_receptiveness(state)
        deck_clean = (
            'incoherence_reckoning' not in auto.trap_flags
            and p.get('ask_sizing') == 'well_sized'
            and p.get('hostile_question_handled') == 'defended'
            and p.get('business_case') == 'board_language'
        )

        if receptiveness == 'supportive' and deck_clean:
            verdict = 'granted'
        elif receptiveness == 'hostile':
            verdict = 'confidence_lost'
        else:
            verdict = 'denied'

        arc = _arc(state)
        state['flags']['board_verdict'] = verdict
        state['flags']['arc_coherence_settled'] = arc
        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'the_audit',
            'choices': p,
            'trap_flags': auto.trap_flags,
            'board_verdict': verdict,
            'receptiveness': receptiveness,
            'arc_coherence': arc,
        })
        validate_run_state(state)
        return state


def _arc(state: dict):
    return arc_coherence(
        state['through_lines']['coherence'].get('drift_events', []),
        state['through_lines']['coherence'].get('anchor_strength'),
    )
