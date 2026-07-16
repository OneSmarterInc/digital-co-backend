from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from scoring.config import (
    WEEK1_CAPTURE_PENALTY,
    WEEK1_FERRARO_CAPTURED,
    WEEK1_NEGLECT_SEED,
    WEEK1_PETRILLO_GAIN,
    WEEK1_POSTURE_SEED,
    WEEK1_PREMATURE_PENALTY,
    WEEK1_SOUND_PATH_BONUS,
    WEEK1_TRAP_PENALTY,
    WEEK1_TRUST_GAIN,
)

from .modules import WeekModule
from .structures import (
    Artifact,
    AutoScore,
    Briefing,
    DecisionField,
    DecisionSpec,
    WeekAdvisorContext,
)


class Week1Module(WeekModule):
    week_number = 1
    title = 'The Inheritance'

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Read Bryce\'s promises against the dashboards, not in isolation.',
                'The most persuasive executive may also be protecting their own position.',
                'Look for one early move that creates visibility without foreclosing strategy.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'You arrive as DigitalCo\'s newly hired CIO, brought in to salvage a digital bet '
                'that has gone sideways. Ray Calloway gives you a bold but careful mandate: '
                '"Take thirty days, get me a real read, and come back with a direction I can take '
                'to the board." Beneath that sits Tom Bryce\'s inheritance: a stalled S/4HANA '
                'migration, a connected-products platform shipping telematics without monetizing '
                'them, a data swamp, a factory floor IT cannot see into, and a depleted IT org. '
                'The private-equity firm wants returns, the founding family is wary, and Marisa '
                'Chen expects movement at the next board meeting.'
            ),
            exec_reads=[
                (
                    'Ray Calloway, CEO: repeats the bold-and-vague mandate and watches whether '
                    'you press for specifics or fill the vacuum. He wants the data bet but will '
                    'not say so until he has cover.'
                ),
                (
                    'Doug Reinhardt, CFO: skeptical and direct after seeing promises turn into '
                    'overspend. Rigor converts him; more vision does not.'
                ),
                (
                    'Sharon Petrillo, VP Ops: protective of the floor and suspicious IT will leave '
                    'her with a stoppage. How you engage her starts the OT relationship.'
                ),
                (
                    'Carl Ferraro, CRO: smooth and commercially compelling. Dealers are the '
                    'business, he argues, and data ambitions could spook the channel.'
                ),
                (
                    'Lena Fischer, Chief Product: proud of connected machines and protective of '
                    'the platform as engineering capability.'
                ),
                (
                    'Gloria Tran, GC: quiet unless asked; machine-data ownership is legal as well '
                    'as strategic.'
                ),
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Application Portfolio Map',
                body=(
                    'IBM i still runs order management and core plant systems in RPG with Aldon '
                    'change control. S/4HANA sits beside it half-migrated. Connected-products runs '
                    'on a hyperscaler with its own pipeline, while scattered BI tools feed a data '
                    'lake that has become a dumping ground. Nothing meaningful has been retired, '
                    'so DigitalCo pays to run the old and the new at once. The portfolio also shows '
                    'plant systems and connected fleet telemetry outside normal IT visibility.'
                ),
            ),
            Artifact(
                title='Project Dashboards',
                body=(
                    'S/4 is red, roughly two years late and over $40M against an original budget '
                    'near $25M, stuck on legacy-to-core dependencies nobody mapped. '
                    'Connected-products is amber: three years in, telematics on about 40% of the '
                    'eligible fleet, rising run cost, near-zero monetization, and dealer complaints '
                    'about data access. The IT org chart shows elevated attrition, a thin bench, '
                    'and only one or two people who still understand the IBM i codebase.'
                ),
            ),
            Artifact(
                title='Digital Spend and Return Budget',
                body=(
                    'The budget stacks digital spend against promised returns. It shows spend '
                    'continuing across S/4, connected-products, cloud run cost, integrator work, '
                    'and fragmented analytics, while the benefits case has not materialized.'
                ),
            ),
            Artifact(
                title='Tom Bryce Transformation Deck',
                body=(
                    'Bryce promised a single digital core, data-driven services, board-visible '
                    'growth, and rapid retirement of legacy cost. The deck is ambitious and weak '
                    'on sequencing. Its gap with the dashboards is the clearest explanation of '
                    'what the new CIO inherited.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        contexts = {
            'diane_brandt': WeekAdvisorContext(
                facts=[
                    'The team has thirty days to produce a board-ready read.',
                    'Calloway signaled more than he explicitly said.',
                    'A strategy thesis matters more than a to-do list.',
                ],
                stance='Work by question. Push the team to define the real problem before acting.',
                signal='Motion mistaken for progress is the week\'s central danger.',
                misdirection='Do not let caution become paralysis.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=[
                    'S/4 stalled because legacy dependencies were never mapped.',
                    'Connected-products has its own hyperscaler pipeline.',
                ],
                stance='Architecture and dependency mapping before irreversible commitments.',
                signal='Ask what breaks when the fleet and data platform scale.',
                misdirection='Do not turn architecture hygiene into a reason to avoid business choices.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=[
                    'Factory-floor systems are a black box to IT.',
                    'Connected fleet telemetry expands the attack surface.',
                ],
                stance='Quietly surface the security and OT exposure.',
                signal=(
                    'For undergrad, be more direct that visibility is an early credibility move.'
                    if tier == Tier.UNDERGRAD else
                    'State the exposure once; do not chase the team if they ignore it.'
                ),
                misdirection='Do not label an optimal answer or invent breach facts.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[
                    'The installed base is a genuine strategic asset.',
                    'Rivals are becoming data companies.',
                ],
                stance='Frame the opportunity and the temptation to commit boldly.',
                signal='Destination may be right even when timing is premature.',
                misdirection='Do not erase the operating inheritance underneath the opportunity.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=[
                    'Hyperscaler commitments sit under connected-products.',
                    'The S/4 integrator agreement already has bad-term risk.',
                ],
                stance='Expose lock-in and contract constraints without resolving them yet.',
                signal='The team should notice commitments before adding new ones.',
                misdirection='Do not overstate current lock-in as already terminal.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=[
                    'Connected-products could become a data-and-services business.',
                    'Rivals are piloting machine-data services.',
                ],
                stance='Supply future-state imagination and energy.',
                signal='Discount hype without killing the strategic possibility.',
                misdirection='Do not let excitement become premature commitment.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=['DigitalCo has inherited an overextended transformation portfolio.'],
            stance='Stay in lane and help the team weigh Week 1 tradeoffs.',
            signal='Synthesis matters more than surrendering to one voice.',
            misdirection='Do not reveal an optimal answer.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(
                key='current_state_assessment',
                label='Current-state assessment',
                field_type='textarea',
            ),
            DecisionField(
                key='strategy_statement',
                label='Strategy statement',
                field_type='textarea',
            ),
            DecisionField(
                key='connected_products_disposition',
                label='Connected-products disposition',
                choices=[
                    {'value': 'continue', 'label': 'Continue'},
                    {'value': 'pause_assess', 'label': 'Pause and assess'},
                    {'value': 'kill', 'label': 'Kill'},
                ],
                trap_choices=['kill'],
            ),
            DecisionField(
                key='s4_disposition',
                label='S/4 disposition',
                choices=[
                    {'value': 'commit_finish', 'label': 'Commit to finish'},
                    {'value': 'stabilize_map', 'label': 'Stabilize and map dependencies'},
                    {'value': 'descope', 'label': 'Descope'},
                    {'value': 'kill', 'label': 'Kill'},
                ],
                trap_choices=['commit_finish'],
            ),
            DecisionField(
                key='data_strategy_posture',
                label='Data strategy posture',
                choices=[
                    {'value': 'pursue', 'label': 'Pursue'},
                    {'value': 'slow_walk', 'label': 'Slow-walk'},
                    {'value': 'defer', 'label': 'Defer'},
                ],
                trap_choices=['slow_walk'],
            ),
            DecisionField(
                key='early_action',
                label='Early action',
                choices=[
                    {'value': 'ot_visibility_assessment', 'label': 'OT visibility assessment'},
                    {'value': 'other_credibility_move', 'label': 'Other credibility move'},
                    {'value': 'premature_bold_move', 'label': 'Premature bold move'},
                    {'value': 'diagnose_only', 'label': 'Diagnose only'},
                ],
                trap_choices=['premature_bold_move'],
            ),
            DecisionField(
                key='early_action_detail',
                label='Early action detail',
                field_type='textarea',
                required=False,
            ),
            DecisionField(
                key='ot_black_box_engaged',
                label='Engage factory-floor visibility / OT black box',
                field_type='boolean',
                required=False,
            ),
            DecisionField(
                key='primary_stakeholder_anchor',
                label='Primary stakeholder anchor',
                choices=[
                    {'value': 'calloway', 'label': 'Calloway'},
                    {'value': 'reinhardt', 'label': 'Reinhardt'},
                    {'value': 'petrillo', 'label': 'Petrillo'},
                    {'value': 'ferraro', 'label': 'Ferraro'},
                    {'value': 'fischer', 'label': 'Fischer'},
                    {'value': 'tran', 'label': 'Tran'},
                    {'value': 'none', 'label': 'None'},
                ],
                trap_choices=['ferraro'],
            ),
        ]
        prompt = (
            'Submit a current-state assessment, strategy statement, structured choices, '
            'and a credible 30-60-90 early-action rationale.'
        )
        if tier == Tier.UNDERGRAD:
            prompt += ' Use the scaffold: what is broken, what matters strategically, what moves first.'
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

        if p.get('connected_products_disposition') == 'kill':
            flags.append('kill_connected_products')
            sj -= WEEK1_TRAP_PENALTY
        if p.get('s4_disposition') == 'commit_finish':
            flags.append('commit_s4_blind')
            sj -= WEEK1_TRAP_PENALTY
        if p.get('data_strategy_posture') == 'slow_walk' or p.get('primary_stakeholder_anchor') == 'ferraro':
            flags.append('ferraro_capture')
            sj -= WEEK1_TRAP_PENALTY

        engaged_ot = _as_bool(p.get('ot_black_box_engaged')) or p.get('early_action') == 'ot_visibility_assessment'
        disciplined_s4 = p.get('s4_disposition') in ('stabilize_map', 'descope')
        if p.get('early_action') == 'ot_visibility_assessment' and disciplined_s4 and not flags:
            sj += WEEK1_SOUND_PATH_BONUS

        if engaged_ot:
            ec += WEEK1_PETRILLO_GAIN
        if 'ferraro_capture' in flags:
            ec -= WEEK1_CAPTURE_PENALTY
        if p.get('early_action') == 'premature_bold_move':
            ec -= WEEK1_PREMATURE_PENALTY

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec},
            trap_flags=flags,
            components={
                'connected_products_disposition': p.get('connected_products_disposition'),
                's4_disposition': p.get('s4_disposition'),
                'data_strategy_posture': p.get('data_strategy_posture'),
                'early_action': p.get('early_action'),
                'engaged_ot': engaged_ot,
                'primary_stakeholder_anchor': p.get('primary_stakeholder_anchor'),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        state['coherence_anchor'] = _strategy_statement(submission)
        state['through_lines']['coherence']['anchor_set'] = True

        engaged_ot = _as_bool(p.get('ot_black_box_engaged')) or p.get('early_action') == 'ot_visibility_assessment'
        if engaged_ot:
            state['through_lines']['security_ot']['posture'] += WEEK1_POSTURE_SEED
            state['relationships']['petrillo'] += WEEK1_TRUST_GAIN
        else:
            state['through_lines']['security_ot']['neglect'] += WEEK1_NEGLECT_SEED

        if 'ferraro_capture' in auto.trap_flags:
            state['relationships']['ferraro'] = WEEK1_FERRARO_CAPTURED
        if p.get('early_action') == 'premature_bold_move':
            state['relationships']['calloway'] -= 1

        if 'kill_connected_products' in auto.trap_flags:
            state['flags']['connected_products_killed'] = True
        if 'commit_s4_blind' in auto.trap_flags:
            state['flags']['s4_precommitted'] = True

        state['through_lines']['cloud_lockin']['notes'].append(
            'Hyperscaler + S/4 integrator contracts flagged in Week 1'
        )
        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'inheritance',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state

    def reads_state(self) -> list[str]:
        return []


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)


def _strategy_statement(submission):
    value = submission.structured_payload.get('strategy_statement')
    if value:
        return value.strip()
    return submission.deliverable_text.strip()
