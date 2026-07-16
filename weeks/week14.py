from copy import deepcopy
from typing import Optional

from core.models import Tier
from core.state import validate_run_state
from engine.climax import accumulated_scars, generate_debrief, resolve_endgame
from scoring.config import (
    WEEK14_GROUNDED_BONUS,
    WEEK14_HONESTY_BONUS,
    WEEK14_INTEGRATION_BONUS,
    WEEK14_PARTIAL_PENALTY,
    WEEK14_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week14Module(WeekModule):
    week_number = 14
    title = 'The Synthesis'

    def reads_state(self) -> list[str]:
        return [
            'accumulated_scores',
            'gates',
            'flags.board_verdict',
            'flags.arc_coherence_settled',
            'flags',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'benchmarks.latest',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Integrate the course frameworks across the whole arc.',
                'Name consequences honestly before proposing the next chapter.',
                'A synthesis can only claim the position the team actually built.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The board has decided, the crises are behind the team, and the CIO must now '
                'explain what DigitalCo became. The deliverable is an integrated account of the '
                'strategy, architecture, data position, AI bet, trust posture, security floor, '
                'cloud economics, and leadership record accumulated across fourteen weeks. The '
                'question is whether the transformation cohered into a defensible data-and-AI '
                'advantage or remained a sequence of expensive reactions.'
            ),
            exec_reads=[
                'The board verdict is settled; the synthesis explains the record rather than relitigating it.',
                'The strongest final strategy starts from the position actually earned.',
                'Scars weaken a victory narrative but strengthen an honest reckoning.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Fourteen-Week Record',
                body='The accumulated decisions, scores, gates, relationships, and through-lines are now the evidence base.',
            ),
            Artifact(
                title='Consequence Reckoning',
                body='Breach outcomes, lock-in, budget credibility, trust, and board judgment must be owned rather than hidden.',
            ),
            Artifact(
                title='Forward Position',
                body='The next strategy must be grounded in the capabilities, constraints, and credibility DigitalCo actually holds.',
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        tier_outcome = resolve_endgame(run_state)
        scars = accumulated_scars(run_state)
        contexts = {
            'diane_brandt': WeekAdvisorContext(
                facts=[f'Endgame ceiling now resolves as: {tier_outcome}', f'Accumulated scars: {scars}'],
                stance='Make the team synthesize the strategy it played, not the one it wishes it had played.',
                signal='A strategy is the sum of choices, not the story told at the end.',
                misdirection='Do not let rhetoric erase drift, gates, or scars.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Data advantage: {run_state.get("flags", {}).get("data_advantage")}'],
                stance='Translate the final position into a credible competitive argument.',
                signal='The forward strategy must start from the real position.',
                misdirection='Do not describe an unbuilt company.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=[f'Infrastructure sustainable: {run_state.get("flags", {}).get("infra_sustainable")}'],
                stance='Keep the technical claims honest and tied to business capability.',
                signal='Overclaiming technical maturity weakens the synthesis.',
                misdirection='Do not hide architecture debt behind transformation language.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Endgame ceiling now resolves as: {tier_outcome}'],
            stance='Help the team remember the arc and account for it honestly.',
            signal='The finale reveals continuity.',
            misdirection='Do not invent a cleaner record.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='synthesis_rationale', label='Synthesis rationale', field_type='textarea'),
            DecisionField(
                key='integration',
                label='Integration',
                choices=[
                    {'value': 'genuine', 'label': 'Genuine'},
                    {'value': 'papered_over', 'label': 'Papered over'},
                ],
                trap_choices=['papered_over'],
            ),
            DecisionField(
                key='consequence_reckoning',
                label='Consequence reckoning',
                choices=[
                    {'value': 'honest', 'label': 'Honest'},
                    {'value': 'victory_narrative', 'label': 'Victory narrative'},
                ],
                trap_choices=['victory_narrative'],
            ),
            DecisionField(
                key='forward_strategy',
                label='Forward strategy',
                choices=[
                    {'value': 'grounded_in_real_position', 'label': 'Grounded in real position'},
                    {'value': 'describes_unbuilt_company', 'label': 'Describes unbuilt company'},
                ],
                trap_choices=['describes_unbuilt_company'],
            ),
        ]
        prompt = 'Submit the final integrated strategic synthesis, consequence reckoning, and forward strategy.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Explicitly connect the synthesis to the course frameworks.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0
        arc = run_state.get('flags', {}).get('arc_coherence_settled')

        if p.get('integration') == 'papered_over' or arc == 'weak':
            flags.append('isolated_decisions')
            coh -= WEEK14_TRAP_PENALTY
        else:
            coh += WEEK14_INTEGRATION_BONUS

        scars = accumulated_scars(run_state)
        if p.get('consequence_reckoning') == 'victory_narrative' and scars:
            flags.append('dishonest_reckoning')
            ec -= WEEK14_TRAP_PENALTY
        elif p.get('consequence_reckoning') == 'honest':
            ec += WEEK14_HONESTY_BONUS

        if p.get('forward_strategy') == 'grounded_in_real_position':
            sj += WEEK14_GROUNDED_BONUS
        elif p.get('forward_strategy') == 'describes_unbuilt_company':
            flags.append('ungrounded_forward')
            sj -= WEEK14_PARTIAL_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'arc_coherence': arc,
                'scars': scars,
                'provisional_endgame_tier': resolve_endgame(run_state),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        state = deepcopy(run_state)
        self._write_resolution(state, auto)
        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'the_synthesis',
            'choices': submission.structured_payload,
            'trap_flags': auto.trap_flags,
            'endgame_tier': state['flags']['endgame_tier'],
        })
        validate_run_state(state)
        return state

    def finalize_state_update(self, score_record, run_state: dict) -> dict:
        state = deepcopy(run_state)
        self._write_resolution(state)
        validate_run_state(state)
        return state

    def _write_resolution(self, state: dict, auto: Optional[AutoScore] = None):
        state['flags']['endgame_tier'] = resolve_endgame(state, auto)
        state['debrief'] = generate_debrief(state)
