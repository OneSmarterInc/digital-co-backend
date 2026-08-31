from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import contradicts, derive_wk1_direction, extends
from scoring.config import (
    WEEK2_CONTINUITY_BONUS,
    WEEK2_COVER_BONUS,
    WEEK2_DISCIPLINE_GAIN,
    WEEK2_DRIFT_PENALTY,
    WEEK2_EXPOSURE_COST,
    WEEK2_GOVERNANCE_BONUS,
    WEEK2_MUSH_COHERENCE_PENALTY,
    WEEK2_PATRON_GAIN,
    WEEK2_STRUCTURE_PENALTY,
    WEEK2_TRAP_PENALTY,
    WEEK2_WEAK_ANCHOR_CAP,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week2Module(WeekModule):
    week_number = 2
    title = 'The Alignment Confrontation'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'relationships',
            'through_lines.security_ot',
            'decision_history',
            'flags',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Calloway may be more committed privately than he sounds publicly.',
                'A split-the-difference answer can be less aligned than a disciplined choice.',
                'Governance is not paperwork here; it is how the strategy survives factions.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'Calloway convenes a strategy session to produce one IT direction he can take '
                'to the board. Reinhardt pushes stabilization, core proof, and discipline before '
                'another dollar goes into the digital bet. The transformation pull, carried by '
                'Chen and the installed-base logic, pushes toward data-and-services now. Ashby '
                'worries about heritage, Petrillo about the floor, Ferraro about the channel, and '
                'Fischer about whether connected-products is being supported or annexed. Calloway '
                'does not referee. He watches the CIO to see whether they can read the room and '
                'give him a direction he can champion.'
            ),
            exec_reads=[
                'Calloway: publicly careful, privately waiting for a survivable bold direction.',
                'Reinhardt: the brake; persuadable by stage-gated discipline, not another vision.',
                'Chen: board pressure for the digital bet to move.',
                'Ashby: heritage concern; the bold bet must be made survivable.',
                'Petrillo: wants to know what the strategy means for her floor.',
                'Ferraro: alert to threats against the dealer channel.',
                'Fischer: watching whether connected-products remains an engineering ally or becomes an IT annex.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        cue = ''
        if tier == Tier.UNDERGRAD:
            cue = ' The positions are deliberately polarized; do not average them into mush.'
        return [
            # Both plans argue from the Week 1 exhibits — the portfolio map, the
            # P&L, the unit-economics worksheet and the industry note. Before
            # this they named the two directions in two sentences each, which
            # let a firm tell them apart but not cost one against the other,
            # and costing them against each other is the whole of Week 2.
            Artifact(
                title='Rival Strategy Plan: Stabilize and Optimize',
                body=(
                    "Circulated by the CFO's office.\n\n"
                    'Read two rows of the portfolio map together. S/4HANA runs $6.8M a year, is '
                    'partial after three years, and has no retirement date. The order management '
                    'core it was supposed to replace still runs $3.1M a year, and its retirement '
                    'column says "none planned — S/4 target, stalled." DigitalCo is paying $9.9M '
                    'annually to run two ERP estates because a migration stopped halfway. Now read '
                    'the P&L. Digital and IT spend went from $19.4M to $27.1M while EBITDA margin '
                    'fell from 11.4% to 9.8%, and digital services revenue reached $1.9M against '
                    'the $12M this programme promised would be here by now. The $9M '
                    'working-capital release is also unrealized; inventory days went 118 to 124.\n\n'
                    'What the plan does. Finish or cleanly retire S/4 and stop paying for two '
                    'estates, which is the largest single recoverable cost in the portfolio. '
                    'Consolidate BI tooling, proposed twice and never funded. Hold connected '
                    'products at its current 12,550 units rather than funding growth in a service '
                    'that loses $184 per unit per year. Deliver the working-capital release using '
                    'systems the company already owns. Return to the data question when digital '
                    'services can show a paying customer at a price that covers cost.\n\n'
                    'What it costs. Meridian is at 43% attach and $26.8M services ARR and will not '
                    'wait. Halberd is at 44% and moving faster on the low end. Two years of '
                    'discipline may mean the installed-base opportunity is contested by the time '
                    'DigitalCo returns to it. The plan accepts that.\n\n'
                    'What it rules out. Any funding request this year that does not reduce cost or '
                    'deliver revenue within twelve months.'
                    + cue
                ),
            ),
            Artifact(
                title='Rival Strategy Plan: Transform to Data and Services',
                body=(
                    'Circulated by the office of the Chief Product Officer.\n\n'
                    'The cost problem is real and it is being read wrong. Platform run cost is '
                    '$4.2M and largely fixed. The marginal cost of an added connected unit is '
                    'roughly $60 a year. DigitalCo has 31,400 telematics-capable units in the '
                    'field and 12,550 connected — 40% of the capable fleet. Every capable unit not '
                    'connected is $60 of cost avoided and $151 to $439 of revenue foregone.\n\n'
                    'That is the argument. Meridian earns $439 per connected unit, Halberd $374, '
                    'DigitalCo $151, on a platform the industry note says costs roughly the same '
                    'to serve either way. The $184 loss per unit is a verdict on a price set once '
                    'and never revisited, against a fleet that was never fully connected.\n\n'
                    'What the plan does. Reprice toward the industry band of $300 to $520. Connect '
                    'the capable fleet, taking attach from 40% of capable toward the 55 to 70% the '
                    'note describes for leaders. Fund connected products as the platform rather '
                    'than as an experiment. Settle data rights with the dealers now, while the '
                    'company still has something to trade. Protect core operations enough to keep '
                    'the plants running, but stop treating the ERP migration as the company\'s '
                    'strategic question.\n\n'
                    'What it costs. Three things. The channel decides whether this works, and '
                    'every OEM that tried to monetize machine data over the dealer\'s head has '
                    'paid for it in orders. The fleet telemetry pipeline has never been '
                    'security-reviewed by IT and has no IT visibility at all, so scaling attach '
                    'scales an unreviewed pipeline. And the plan asks the board for patience at '
                    '9.8% margin, which is when patience is hardest to get.\n\n'
                    'What it rules out. Waiting. The capital cost of a competitive platform is '
                    'flat regardless of fleet size, which favours scale or partnership. Two more '
                    'years at current attach makes DigitalCo the junior partner in someone '
                    "else's platform."
                    + cue
                ),
            ),
            Artifact(
                title='Missing Artifact: IT Governance',
                body=(
                    'There is no real standing governance model. Bryce ran by personality and ad hoc '
                    'deal: no steering structure, no stage gates, no legitimate way for factions to '
                    'engage a decision rather than fight it in the hallway.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        anchor = run_state.get('coherence_anchor') or 'No useful Week 1 anchor was recorded.'
        wk1_direction = derive_wk1_direction(run_state)
        contexts = {
            'diane_brandt': WeekAdvisorContext(
                facts=[
                    f'Week 1 anchor: {anchor}',
                    f'Derived Week 1 direction: {wk1_direction}',
                    'Calloway is watching whether the CIO can read what he wants without exposing him.',
                ],
                stance='Separate what Calloway said from what he needs covered.',
                signal='A strategy trying to satisfy every faction will have no spine.',
                misdirection='Do not let political reading become refusal to commit.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[
                    f'Derived Week 1 direction: {wk1_direction}',
                    'The installed-base data-services opportunity remains strategically live unless Week 1 killed it.',
                ],
                stance='Argue for committing the company around data-and-services.',
                signal='The destination may be right, but survivability and governance decide whether it holds.',
                misdirection='Do not push a raw bold bet that Calloway cannot sell.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['Governance has to be something architecture can deliver against.', 'S/4 dependencies remain real.'],
                stance='Press for stage gates, accountable sequencing, and delivery realism.',
                signal='Alignment around impossible architecture is not alignment.',
                misdirection='Do not make architecture the strategy.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=[
                    f'Security/OT posture: {run_state["through_lines"]["security_ot"]["posture"]}',
                    f'Security/OT neglect: {run_state["through_lines"]["security_ot"]["neglect"]}',
                    'Factory-floor exposure is not resolved by an alignment meeting.',
                ],
                stance='Keep the unresolved OT exposure visible without hijacking the week.',
                signal='The warning stands regardless of which strategy wins.',
                misdirection='Do not invent a new breach or solve Week 10 now.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=['A coherent direction strengthens later vendor negotiation.', 'Vendor decisions are coming.'],
                stance='Connect alignment to future bargaining leverage.',
                signal='Unclear strategy weakens every vendor conversation.',
                misdirection='Do not over-focus on contracts before the direction is set.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['A vivid future-state can help sell transformation.', 'The board needs a survivable story.'],
                stance='Help imagine the data-services future while discounting hype.',
                signal='Vision sells better when governance makes it credible.',
                misdirection='Do not let excitement flatten the heritage and channel concerns.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Week 1 anchor: {anchor}', f'Derived Week 1 direction: {wk1_direction}'],
            stance='Help the team align around a direction that can survive the room.',
            signal='Continuity with Week 1 matters.',
            misdirection='Do not reveal an optimal answer.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(
                key='alignment_rationale',
                label='Alignment and governance brief',
                field_type='textarea',
            ),
            DecisionField(
                key='alignment_choice',
                label='Alignment choice',
                choices=[
                    {'value': 'stabilize', 'label': 'Stabilize'},
                    {'value': 'transform_data_services', 'label': 'Transform to data and services'},
                    {'value': 'balanced_split', 'label': 'Balanced split'},
                ],
                trap_choices=['balanced_split'],
            ),
            DecisionField(key='governance_included', label='Governance included', field_type='boolean', required=False),
            DecisionField(
                key='governance_has_stage_gates',
                label='Governance has stage gates',
                field_type='boolean',
                required=False,
            ),
            DecisionField(
                key='governance_gives_business_voice',
                label='Governance gives business voice',
                field_type='boolean',
                required=False,
            ),
            DecisionField(
                key='calloway_positioning',
                label='Calloway positioning',
                choices=[
                    {'value': 'team_recommendation_with_cover', 'label': 'Team recommendation with cover'},
                    {'value': 'propose_safe_stabilization', 'label': 'Propose safe stabilization'},
                    {'value': 'push_bold_raw', 'label': 'Push bold raw'},
                ],
                trap_choices=['propose_safe_stabilization', 'push_bold_raw'],
            ),
        ]
        prompt = 'Submit an aligned IT strategy, governance mechanism, and political positioning for Calloway.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Name the alignment and governance lenses you are applying.'
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

        if p.get('alignment_choice') == 'balanced_split':
            flags.append('mush')
            sj -= WEEK2_TRAP_PENALTY
        if not (_as_bool(p.get('governance_included')) and _as_bool(p.get('governance_has_stage_gates'))):
            flags.append('no_governance')
            sj -= WEEK2_STRUCTURE_PENALTY
        if p.get('calloway_positioning') == 'propose_safe_stabilization':
            flags.append('calloway_misread_safe')
            sj -= WEEK2_TRAP_PENALTY
        if p.get('calloway_positioning') == 'push_bold_raw' and not _as_bool(p.get('governance_included')):
            flags.append('calloway_exposed')
            sj -= WEEK2_TRAP_PENALTY

        if p.get('calloway_positioning') == 'team_recommendation_with_cover':
            ec += WEEK2_COVER_BONUS
        if _as_bool(p.get('governance_gives_business_voice')):
            ec += WEEK2_GOVERNANCE_BONUS

        anchor_strength = run_state['through_lines']['coherence'].get('anchor_strength') or 'adequate'
        wk1_dir = derive_wk1_direction(run_state)
        choice = p.get('alignment_choice')
        if choice == 'balanced_split':
            coh -= WEEK2_MUSH_COHERENCE_PENALTY
        elif wk1_dir != 'ambiguous' and contradicts(choice, wk1_dir):
            coh -= WEEK2_DRIFT_PENALTY
            flags.append('coherence_drift')
        elif extends(choice, wk1_dir):
            bonus = WEEK2_CONTINUITY_BONUS
            if anchor_strength == 'weak':
                bonus = min(bonus, WEEK2_WEAK_ANCHOR_CAP)
            coh += bonus

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'alignment_choice': choice,
                'calloway_positioning': p.get('calloway_positioning'),
                'wk1_direction': wk1_dir,
                'anchor_strength': anchor_strength,
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        if p.get('calloway_positioning') == 'team_recommendation_with_cover':
            state['relationships']['calloway'] += WEEK2_PATRON_GAIN
            state['flags']['calloway_patron'] = True
        elif 'calloway_exposed' in auto.trap_flags:
            state['relationships']['calloway'] -= WEEK2_EXPOSURE_COST

        if _as_bool(p.get('governance_has_stage_gates')):
            state['relationships']['reinhardt'] += WEEK2_DISCIPLINE_GAIN

        state['flags']['governance_built'] = bool(
            _as_bool(p.get('governance_included')) and _as_bool(p.get('governance_has_stage_gates'))
        )

        if 'coherence_drift' in auto.trap_flags or 'mush' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'mush' if 'mush' in auto.trap_flags else 'drift',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'alignment',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)
