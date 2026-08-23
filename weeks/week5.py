from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import derive_wk1_direction
from scoring.config import (
    WEEK5_CONVICTION_BONUS,
    WEEK5_DRIFT_PENALTY,
    WEEK5_HOLD_BONUS,
    WEEK5_DISRUPTION_READ_BONUS,
    WEEK5_TRAP_PENALTY,
)
from scoring.models import Benchmark

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week5Module(WeekModule):
    week_number = 5
    title = 'The Read'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'benchmarks.latest',
            'through_lines.cloud_lockin',
            'relationships',
        ]

    def briefing_for_run(self, tier: Tier, run) -> Briefing:
        return self.briefing(tier, standing_pressure=_standing_pressure(run))

    def briefing(self, tier: Tier, standing_pressure='neutral') -> Briefing:
        pressure = {
            'behind': (
                'The Phase 1 benchmark has left your team visibly behind peers, so Meridian\'s '
                'announcement lands with sharper board anxiety and a stronger urge to catch up.'
            ),
            'ahead': (
                'The Phase 1 benchmark gives your team room to breathe, so Meridian\'s announcement '
                'lands as a strategic read rather than a panic order.'
            ),
            'neutral': (
                'The Phase 1 benchmark gives the board fresh context, and Meridian\'s announcement '
                'now tests whether the team can hold a reasoned position under attention.'
            ),
        }[standing_pressure]
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Meridian is a herd-pressure test, not automatic evidence of the right path.',
                'The quieter technologies may be the more disruptive threats.',
                'Use real-options logic rather than all-in or all-out bets.',
            ]
        return Briefing(
            title=self.title,
            body=(
                f'{pressure} Meridian Industrial publicly bets on autonomous equipment and a '
                'sweeping digital-twin platform, with vendors and analysts amplifying the story. '
                'At the same time, additive manufacturing threatens parts economics quietly, and '
                'edge AI makes low-end connected competitors more plausible. The task is to read '
                'the landscape and separate real disruption from dazzle.'
            ),
            exec_reads=[
                'Chen: wants DigitalCo seen moving after Meridian made headlines.',
                'Whitfield: excited by the bold bet and useful as an ally, but vulnerable to FOMO.',
                'Calloway: worries about being out-innovated in public.',
                'Fischer: knows what is feasible and whether the technologies fit DigitalCo\'s platform.',
                'Reinhardt: useful gravity against expensive dazzle, but not a reason to dismiss every threat.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Emerging-Technology Menu',
                body=(
                    'Autonomy and digital twins dominate headlines and vendor demos. Additive '
                    'manufacturing and edge AI look quieter but may alter how DigitalCo makes money '
                    'or how lower-cost competitors attack the market.'
                ),
            ),
            Artifact(
                title='Autonomy and Digital Twins',
                body=(
                    'Autonomy is capital-intensive and years from broad reality in DigitalCo\'s segment. '
                    'Digital twins are impressive in demos but depend on whether DigitalCo has the data '
                    'foundation to make them real.'
                ),
            ),
            Artifact(
                title='Additive Manufacturing and Edge AI',
                body=(
                    'Additive threatens the parts and aftermarket stream. Edge AI lowers the cost of '
                    'good-enough connected features, creating low-end pressure on premium positioning.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        contexts = {
            'zoe_park': WeekAdvisorContext(
                facts=['Meridian is making public noise around autonomy and digital twins.', 'Additive and edge AI are quieter threats.'],
                stance='Bring future-state imagination while helping identify the boring disruptions early.',
                signal='Look past demos and ask how the business model changes.',
                misdirection='Do not let excitement become a chase of Meridian\'s keynote.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['Autonomy is not near-term feasible for the segment.', 'Digital twins require real data foundations.'],
                stance='Counter dazzle with feasibility and implementation realism.',
                signal='A cool demo is not an operating capability.',
                misdirection='Do not dismiss genuine disruption as toys.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Derived Week 1 direction: {derive_wk1_direction(run_state)}'],
                stance='Resolve the Zoe/Marcus tension through business-model impact.',
                signal='Ask whether the technology changes how DigitalCo makes money or loses it.',
                misdirection='Do not equate boldness with chasing a rival.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['The team has a prior strategy and Phase 1 benchmark pressure.'],
                stance='Ask whether DigitalCo is about to run strategy from Meridian\'s press release.',
                signal='Coherence under public pressure matters.',
                misdirection='Do not make calmness into complacency.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=['Autonomous and connected equipment expand attack surface.'],
                stance='Keep security implications visible as technology choices broaden.',
                signal='New capabilities carry new control surfaces.',
                misdirection='Do not turn the week into a security-only decision.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=['Vendors are circling with demos and platform promises.'],
                stance='Stay light; remind the team that vendor dazzle has incentives underneath it.',
                signal='Ask who benefits if DigitalCo chases the demo.',
                misdirection='Do not make every vendor signal suspect.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=['Meridian has created public herd pressure.'],
            stance='Help the team separate signal from hype.',
            signal='Business-model impact decides the read.',
            misdirection='Do not reveal an optimal portfolio.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        choices = [
            {'value': 'bet', 'label': 'Bet'},
            {'value': 'pilot', 'label': 'Pilot'},
            {'value': 'watch', 'label': 'Watch'},
            {'value': 'ignore', 'label': 'Ignore'},
        ]
        fields = [
            DecisionField(key='technology_read', label='Emerging-technology read', field_type='textarea'),
            DecisionField(key='portfolio.autonomy', label='Autonomy', choices=choices),
            DecisionField(key='portfolio.digital_twins', label='Digital twins', choices=choices),
            DecisionField(key='portfolio.additive_manufacturing', label='Additive manufacturing', choices=choices),
            DecisionField(key='portfolio.edge_ai_low_end', label='Edge AI / low end', choices=choices),
            DecisionField(
                key='innovation_capability',
                label='Innovation capability',
                choices=[
                    {'value': 'separate_group', 'label': 'Separate group'},
                    {'value': 'embedded', 'label': 'Embedded'},
                ],
            ),
            DecisionField(
                key='meridian_response',
                label='Meridian response',
                choices=[
                    {'value': 'chase', 'label': 'Chase'},
                    {'value': 'ignore', 'label': 'Ignore'},
                    {'value': 'strategic_conviction', 'label': 'Strategic conviction'},
                ],
                trap_choices=['chase'],
            ),
        ]
        prompt = 'Submit a real-options technology portfolio and a response to Meridian.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply disruptive-versus-sustaining, hype-cycle, and real-options lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = _normalize_payload(submission.structured_payload)
        portfolio = p['portfolio']
        flags = []
        sj = 0
        ec = 0
        coh = 0

        chasing_dazzle = portfolio['autonomy'] == 'bet' or portfolio['digital_twins'] == 'bet'
        saw_real = portfolio['additive_manufacturing'] in ('bet', 'pilot') and portfolio['edge_ai_low_end'] in ('bet', 'pilot')
        dismissed_real = portfolio['additive_manufacturing'] == 'ignore' and portfolio['edge_ai_low_end'] == 'ignore'

        if chasing_dazzle and p['meridian_response'] == 'chase':
            flags.append('chased_dazzle')
            sj -= WEEK5_TRAP_PENALTY
        if dismissed_real:
            flags.append('complacency')
            sj -= WEEK5_TRAP_PENALTY
        if saw_real and not chasing_dazzle:
            sj += WEEK5_DISRUPTION_READ_BONUS

        if p['meridian_response'] == 'strategic_conviction':
            ec += WEEK5_CONVICTION_BONUS
        elif p['meridian_response'] == 'chase':
            flags.append('herd_chase')
            ec -= WEEK5_TRAP_PENALTY

        wk1_direction = derive_wk1_direction(run_state)
        if wk1_direction == 'data_services' and (portfolio['autonomy'] == 'bet' or p['meridian_response'] == 'chase'):
            coh -= WEEK5_DRIFT_PENALTY
            flags.append('herd_pivot')
        elif wk1_direction == 'data_services' and p['meridian_response'] == 'strategic_conviction':
            # The same axis, held: the rival's announcement did not move them off
            # the direction they set in week 1. Exactly the case the penalty
            # above detects, with the sign inverted.
            coh += WEEK5_HOLD_BONUS

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'portfolio': portfolio,
                'innovation_capability': p['innovation_capability'],
                'meridian_response': p['meridian_response'],
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = _normalize_payload(submission.structured_payload)
        portfolio = p['portfolio']
        state = deepcopy(run_state)

        state['flags']['additive_threat_recognized'] = portfolio['additive_manufacturing'] != 'ignore'
        state['flags']['innovation_capability'] = p['innovation_capability']
        state['flags']['meridian_chased'] = p['meridian_response'] == 'chase'

        if 'chased_dazzle' in auto.trap_flags:
            state['relationships']['fischer'] -= 1
        elif portfolio['additive_manufacturing'] in ('bet', 'pilot'):
            state['relationships']['fischer'] += 1

        if 'herd_pivot' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({'week': self.week_number, 'kind': 'herd_pivot'})

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'disruption_read',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state


def _normalize_payload(payload):
    if 'portfolio' in payload:
        return payload
    return {
        **payload,
        'portfolio': {
            'autonomy': payload.get('portfolio.autonomy'),
            'digital_twins': payload.get('portfolio.digital_twins'),
            'additive_manufacturing': payload.get('portfolio.additive_manufacturing'),
            'edge_ai_low_end': payload.get('portfolio.edge_ai_low_end'),
        },
    }


def _standing_pressure(run):
    benchmark = Benchmark.objects.filter(cohort=run.team.cohort).order_by('-after_week').first()
    if not benchmark:
        return 'neutral'
    row = next((item for item in benchmark.standings if item.get('team_id') == run.team_id), None)
    if not row:
        return 'neutral'
    team_count = max(len(benchmark.standings), 1)
    rank = row.get('rank', team_count)
    if rank <= max(1, team_count // 3):
        return 'ahead'
    if rank > max(1, (team_count * 2) // 3):
        return 'behind'
    return 'neutral'
