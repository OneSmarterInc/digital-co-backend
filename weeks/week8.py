from copy import deepcopy

from core.models import Tier
from core.state import validate_run_state
from engine.derivations import wk4_cloud_commitment
from scoring.config import (
    WEEK8_CHANNEL_REVOLT,
    WEEK8_KEYSTONE_COHERENCE_BONUS,
    WEEK8_KEYSTONE_COHERENCE_PENALTY,
    WEEK8_LEGAL_EXPOSURE,
    WEEK8_PARTIAL_PENALTY,
    WEEK8_PREDICTIVE_SETUP_BONUS,
    WEEK8_SHARED_VALUE_BONUS,
    WEEK8_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week8Module(WeekModule):
    week_number = 8
    title = 'The Keystone'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'through_lines.data_rights',
            'through_lines.cloud_lockin',
            'gates.security_ot',
            'gates.budget_credibility',
            'relationships',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'A data advantage requires governance, not just ownership language.',
                'The shared-value model protects advantage without creating a channel revolt.',
                'Predictive analytics is the capability the strategy has been pointing toward.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'The data-and-services strategy comes due. DigitalCo has fleet telemetry, a sourced '
                'platform, a fragmented data swamp, and a board that wants the installed base to '
                'become a real advantage. The ownership question is the temptation: DigitalCo, '
                'dealers, and customers all have plausible claims on machine data. Locking up all '
                'the data looks decisive, but Ferraro hears channel revolt and Tran hears legal '
                'exposure. The task is to turn the swamp into a governed asset and build the '
                'predictive capability the strategy has promised since Week 1.'
            ),
            exec_reads=[
                'Chen: wants the data advantage to materialize and may over-read ownership as strength.',
                'Ferraro: warns that dealers will revolt if DigitalCo claims everything.',
                'Tran: names the legal exposure inside an aggressive rights claim.',
                'Fischer: watches whether connected-products data becomes a real capability.',
                'Reinhardt: wants return discipline around another data investment.',
                'Calloway: watches whether the strategic spine is finally real.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return [
            Artifact(
                title='Data Swamp Inventory',
                body=(
                    'Plants and functions still disagree on core definitions. Multiple BI tools, '
                    'an ungoverned lake, and inconsistent installed-base counts prevent advantage.'
                ),
            ),
            Artifact(
                title='Ownership Landscape',
                body=(
                    'DigitalCo built the machines, dealers sell and service them, and customers run '
                    'them. Each party has a plausible claim on the data generated in use.'
                ),
            ),
            Artifact(
                title='Three Rights Models',
                body=(
                    'A land grab asserts DigitalCo ownership over all data. Ducking leaves rights '
                    'ambiguous. Shared value uses aggregate and derived data for advantage while '
                    'returning real value to customers and dealers.'
                ),
            ),
            Artifact(
                title='Analytics Architecture',
                body=(
                    'Descriptive reporting explains what happened. Predictive capability turns fleet '
                    'telemetry into service, maintenance, and performance advantage.'
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        rights = run_state['through_lines']['data_rights'].get('posture')
        cloud = wk4_cloud_commitment(run_state) or 'unknown'
        contexts = {
            'daniel_stern': WeekAdvisorContext(
                facts=['The data is genuinely valuable.', f'Current data-rights posture: {rights}'],
                stance='Make the strongest data-as-advantage case.',
                signal='The advantage thesis is right; maximal ownership is the dangerous overreach.',
                misdirection='Do not confuse owning all data with creating durable advantage.',
            ),
            'marcus_webb': WeekAdvisorContext(
                facts=['The lake is still a swamp without governance.', f'Week 4 cloud commitment: {cloud}'],
                stance='Ground the strategy in governance and predictive architecture.',
                signal='No rights model matters if the data stays ungoverned.',
                misdirection='Do not let architecture diagrams substitute for operating governance.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['Week 8 audits the whole data-and-services spine.'],
                stance='Ask whether the strategy is now operationally real.',
                signal='The keystone must connect the Week 1 promise to a buildable capability.',
                misdirection='Do not reward slogans about data advantage.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=[f'Security gate: {run_state["gates"]["security_ot"]["state"]}'],
                stance='Surface the security blind spot inside the data asset.',
                signal='The data strategy inherits the fleet and OT posture underneath it.',
                misdirection='Do not turn this into a breach scenario.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=['Platform terms and data rights interact.'],
                stance='Keep rights, contracts, and operating reality tied together.',
                signal='The rights posture must survive partners reading it closely.',
                misdirection='Do not reduce this to procurement language.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['Predictive services are the future-facing opportunity.'],
                stance='Keep imagination tied to governed data and feasible analytics.',
                signal='Predictive value is the opportunity; ungoverned ambition is not.',
                misdirection='Do not oversell AI before the data foundation exists.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[f'Current data-rights posture: {rights}', f'Week 4 cloud commitment: {cloud}'],
            stance='Help the team make the data-and-services spine real.',
            signal='Rights, governance, and predictive architecture must fit together.',
            misdirection='Do not reveal future data-rights consequences.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(key='data_strategy_rationale', label='Data strategy rationale', field_type='textarea'),
            DecisionField(
                key='rights_posture',
                label='Rights and ownership posture',
                choices=[
                    {'value': 'land_grab', 'label': 'Land grab'},
                    {'value': 'duck', 'label': 'Duck'},
                    {'value': 'shared_value', 'label': 'Shared value'},
                ],
                trap_choices=['land_grab', 'duck'],
            ),
            DecisionField(key='governance_built', label='Governance built', field_type='boolean', required=False),
            DecisionField(
                key='analytics_architecture',
                label='Analytics architecture',
                choices=[
                    {'value': 'predictive', 'label': 'Predictive'},
                    {'value': 'descriptive_only', 'label': 'Descriptive only'},
                    {'value': 'none', 'label': 'None'},
                ],
                trap_choices=['descriptive_only', 'none'],
            ),
        ]
        prompt = 'Submit the data strategy, rights posture, governance model, and analytics architecture.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply data-governance, data-as-asset, rights, and analytics-maturity lenses.'
        return DecisionSpec(fields=fields, deliverable_prompt=prompt, rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate')

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        p = submission.structured_payload
        flags = []
        sj = 0
        ec = 0
        coh = 0

        if p.get('rights_posture') == 'shared_value' and p.get('analytics_architecture') == 'predictive':
            coh += WEEK8_KEYSTONE_COHERENCE_BONUS
        elif p.get('rights_posture') == 'duck' or p.get('analytics_architecture') != 'predictive':
            coh -= WEEK8_KEYSTONE_COHERENCE_PENALTY

        if p.get('rights_posture') == 'land_grab':
            flags.append('land_grab')
            sj -= WEEK8_TRAP_PENALTY
        elif p.get('rights_posture') == 'duck':
            flags.append('duck')
            sj -= WEEK8_TRAP_PENALTY
        elif p.get('rights_posture') == 'shared_value':
            sj += WEEK8_SHARED_VALUE_BONUS

        if not _as_bool(p.get('governance_built')):
            flags.append('governance_neglect')
            sj -= WEEK8_PARTIAL_PENALTY

        if p.get('analytics_architecture') == 'predictive' and _as_bool(p.get('governance_built')):
            ec += WEEK8_PREDICTIVE_SETUP_BONUS

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'rights_posture': p.get('rights_posture'),
                'governance_built': _as_bool(p.get('governance_built')),
                'analytics_architecture': p.get('analytics_architecture'),
                'prior_data_rights_posture': run_state['through_lines']['data_rights'].get('posture'),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)
        data_rights = state['through_lines']['data_rights']
        prior_posture = data_rights.get('posture')

        if p.get('rights_posture') == 'land_grab':
            converged = prior_posture == 'open_unresolved'
            data_rights['posture'] = 'contested_aggressive' if converged else 'asserted'
            note = 'Data land grab in Week 8 - pre-loads the Week 11 revolt'
            if converged:
                note += '; compounds the Week 6 open platform'
            data_rights['notes'].append(note)
            state['flags']['land_grab'] = True
        elif p.get('rights_posture') == 'shared_value':
            data_rights['posture'] = 'shared_value'
            data_rights['notes'].append('Shared-value data-rights model established in Week 8')

        state['flags']['predictive_built'] = (
            p.get('analytics_architecture') == 'predictive' and _as_bool(p.get('governance_built'))
        )

        if p.get('rights_posture') == 'land_grab':
            state['relationships']['ferraro'] -= WEEK8_CHANNEL_REVOLT
            state['relationships']['tran'] -= WEEK8_LEGAL_EXPOSURE
        elif p.get('rights_posture') == 'shared_value':
            state['relationships']['ferraro'] += 1
            state['relationships']['tran'] += 1

        if 'land_grab' in auto.trap_flags or 'duck' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': p.get('rights_posture'),
                'weight': 'keystone',
            })

        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'data_keystone',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)
