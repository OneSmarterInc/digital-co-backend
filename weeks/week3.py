from copy import deepcopy

from core.models import Tier
from core.state import advance_gate, validate_run_state
from engine.derivations import derive_wk1_direction
from scoring.config import (
    WEEK3_DRIFT_PENALTY,
    WEEK3_FORWARD_BONUS,
    WEEK3_GOVERNANCE_USE_BONUS,
    WEEK3_IMPROVISATION_PENALTY,
    WEEK3_LOCKIN_INCREMENT,
    WEEK3_REINHARDT_CONVERSION,
    WEEK3_REINHARDT_LOSS,
    WEEK3_TRANSPARENCY_BONUS,
    WEEK3_TRAP_PENALTY,
)

from .modules import WeekModule
from .structures import Artifact, AutoScore, Briefing, DecisionField, DecisionSpec, WeekAdvisorContext


class Week3Module(WeekModule):
    week_number = 3
    title = 'The Reckoning'

    def reads_state(self) -> list[str]:
        return [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'flags.s4_precommitted',
            'flags.governance_built',
            'relationships',
            'gates.budget_credibility',
        ]

    def briefing(self, tier: Tier) -> Briefing:
        signals = []
        if tier == Tier.UNDERGRAD:
            signals = [
                'Separate sunk cost from the best path forward.',
                'The integrator lifeline is a tradeoff, not free rescue.',
                'Governance built in Week 2 matters only if it is used under stress.',
            ]
        return Briefing(
            title=self.title,
            body=(
                'A weekend cutover attempt fails. Data migration throws errors, the new core '
                'breaks against the IBM i it was meant to sit beside, and orders cannot be '
                'processed for the better part of a day. Spend has crossed $40M against an '
                'original budget near $25M, the date slips again, and the root cause is still '
                'the unmapped dependency web Marcus warned about. Reinhardt wants the bleeding '
                'stopped, Petrillo wants operations protected, Chen wants accountability, and '
                'Calloway is watching whether the CIO owns the hard call.'
            ),
            exec_reads=[
                'Reinhardt: angry but convertible by rigorous, forward-looking crisis handling.',
                'Chen: wants accountability and a credible path to return on the funded program.',
                'Petrillo: wants disruption to stop and shipment reliability restored.',
                'Calloway: watches for ownership instead of a comforting story.',
            ],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        lifeline_note = ''
        if tier == Tier.UNDERGRAD:
            lifeline_note = ' The promised speed comes with future lock-in and negotiation cost.'
        return [
            Artifact(
                title='True Budget and Schedule',
                body=(
                    'S/4 is now over $40M against an original estimate near $25M. Major dates '
                    'have slipped repeatedly, and every new recovery plan has assumed dependency '
                    'knowledge the program never actually built.'
                ),
            ),
            Artifact(
                title='Cutover Post-Mortem',
                body=(
                    'The cutover failed when migrated data and process flows broke against legacy '
                    'order and plant dependencies. The issue is not simply schedule slippage; the '
                    'new core and legacy core still do not have a mapped boundary.'
                ),
            ),
            Artifact(
                title='Missing Dependency Map',
                body=(
                    'The most important artifact is absent: no complete map of what IBM i owns, '
                    'what S/4 must replace, and what can safely be decoupled. Without it, no one '
                    'can bound what finishing really takes.'
                ),
            ),
            Artifact(
                title='Integrator Accelerator Pitch',
                body=(
                    'The integrator offers a proprietary accelerator and workaround that promises '
                    'a faster cutover for more money and tighter use of its tooling.'
                    + lifeline_note
                ),
            ),
        ]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        s4_precommitted = run_state.get('flags', {}).get('s4_precommitted', False)
        governance = run_state.get('flags', {}).get('governance_built', False)
        precommit_note = (
            'The team pre-committed to finishing S/4 in Week 1 and is now living with that call.'
            if s4_precommitted else
            'The team did not pre-commit to finishing S/4 in Week 1.'
        )
        contexts = {
            'marcus_webb': WeekAdvisorContext(
                facts=[
                    'The cutover failed because S/4 and IBM i dependencies were not mapped.',
                    precommit_note,
                    f'Governance built in Week 2: {governance}',
                ],
                stance='Lead with salvageability and dependency realism.',
                signal='Descope-and-stabilize is viable; a clean kill can be survivable.',
                misdirection='Do not treat the accelerator as understanding the system.',
            ),
            'diane_brandt': WeekAdvisorContext(
                facts=['The $40M is gone regardless of the next decision.', precommit_note],
                stance='Coach sunk-cost discipline and transparent ownership.',
                signal='The only live question is the best path from here.',
                misdirection='Do not let accountability become blame theater.',
            ),
            'frank_delgado': WeekAdvisorContext(
                facts=['The integrator has incentive to sell the proprietary accelerator.'],
                stance='Expose the walk-away cost and future lock-in inside the lifeline.',
                signal='Ask what the accelerator costs later, not only what it saves now.',
                misdirection='Do not imply every integrator option is equally bad.',
            ),
            'daniel_stern': WeekAdvisorContext(
                facts=[f'Derived Week 1 direction: {derive_wk1_direction(run_state)}'],
                stance='Ask whether S/4 is foundation for the strategy or a monument to Bryce.',
                signal='Abandoning legacy work can be right or reckless depending on core stability.',
                misdirection='Do not let strategic boldness ignore operational dependency.',
            ),
            'renata_voss': WeekAdvisorContext(
                facts=[
                    'Failed cutovers can leave inconsistent data states.',
                    'Factory-floor exposure remains unresolved while everyone fights the S/4 fire.',
                ],
                stance='Keep risk visible without hijacking the project-crisis decision.',
                signal='This fire does not make the OT fuse disappear.',
                misdirection='Do not invent a breach.',
            ),
            'zoe_park': WeekAdvisorContext(
                facts=['Week 3 is a lighter innovation week.'],
                stance='Stay light and keep future-state energy bounded by crisis reality.',
                signal='The future still needs a stable core underneath it.',
                misdirection='Do not pitch around the failure.',
            ),
        }
        return contexts.get(advisor_key, WeekAdvisorContext(
            facts=[precommit_note, f'Governance built in Week 2: {governance}'],
            stance='Help the team make a forward-looking project-crisis call.',
            signal='The accelerator is attractive now and costly later.',
            misdirection='Do not reveal an optimal answer.',
        ))

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        fields = [
            DecisionField(
                key='migration_plan',
                label='Migration decision and execution plan',
                field_type='textarea',
            ),
            DecisionField(
                key='migration_fate',
                label='Migration fate',
                choices=[
                    {'value': 'rescue', 'label': 'Rescue existing cutover'},
                    {'value': 'restructure', 'label': 'Restructure'},
                    {'value': 'descope', 'label': 'Descope'},
                    {'value': 'kill', 'label': 'Kill'},
                ],
                trap_choices=['rescue'],
            ),
            DecisionField(
                key='integrator_decision',
                label='Integrator decision',
                choices=[
                    {'value': 'renegotiate', 'label': 'Renegotiate'},
                    {'value': 'replace', 'label': 'Replace'},
                    {'value': 'take_accelerator', 'label': 'Take accelerator'},
                ],
                trap_choices=['take_accelerator'],
            ),
            DecisionField(key='has_execution_plan', label='Has execution plan', field_type='boolean', required=False),
            DecisionField(
                key='communication_posture',
                label='Communication posture',
                choices=[
                    {'value': 'transparent_ownership', 'label': 'Transparent ownership'},
                    {'value': 'blame_shift', 'label': 'Blame shift'},
                    {'value': 'spin', 'label': 'Spin'},
                ],
                trap_choices=['blame_shift', 'spin'],
            ),
        ]
        prompt = 'Submit the S/4 fate decision, execution plan, integrator stance, and board/business communication.'
        if tier == Tier.UNDERGRAD:
            prompt += ' Apply sunk-cost, project-governance, and stage-gating lenses.'
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

        if p.get('migration_fate') == 'rescue':
            flags.append('sunk_cost_pushthrough')
            sj -= WEEK3_TRAP_PENALTY
        if p.get('integrator_decision') == 'take_accelerator':
            flags.append('integrator_lifeline')
            sj -= WEEK3_TRAP_PENALTY
        if p.get('migration_fate') in ('restructure', 'descope', 'kill') and _as_bool(p.get('has_execution_plan')):
            sj += WEEK3_FORWARD_BONUS

        if p.get('communication_posture') == 'transparent_ownership':
            ec += WEEK3_TRANSPARENCY_BONUS
        elif p.get('communication_posture') in ('blame_shift', 'spin'):
            flags.append('blame_shift')
            ec -= WEEK3_TRAP_PENALTY

        if run_state.get('flags', {}).get('governance_built') and _as_bool(p.get('has_execution_plan')):
            ec += WEEK3_GOVERNANCE_USE_BONUS
        elif not run_state.get('flags', {}).get('governance_built'):
            ec -= WEEK3_IMPROVISATION_PENALTY

        wk1_direction = derive_wk1_direction(run_state)
        if wk1_direction == 'data_services' and p.get('migration_fate') == 'rescue':
            coh -= WEEK3_DRIFT_PENALTY
            flags.append('misallocation')

        return AutoScore(
            scores={'strategic_judgment': sj, 'execution_consequence': ec, 'coherence': coh},
            trap_flags=flags,
            components={
                'migration_fate': p.get('migration_fate'),
                'integrator_decision': p.get('integrator_decision'),
                'has_execution_plan': _as_bool(p.get('has_execution_plan')),
                'communication_posture': p.get('communication_posture'),
                'wk1_direction': wk1_direction,
                'governance_built': run_state.get('flags', {}).get('governance_built', False),
            },
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        p = submission.structured_payload
        state = deepcopy(run_state)

        if p.get('integrator_decision') == 'take_accelerator':
            state['flags']['integrator_accelerator_taken'] = True
            state['through_lines']['cloud_lockin']['depth'] += WEEK3_LOCKIN_INCREMENT
            state['through_lines']['cloud_lockin']['notes'].append(
                'Integrator accelerator taken in Week 3 - detonates Weeks 7 and 12'
            )

        if 'misallocation' in auto.trap_flags:
            state['through_lines']['coherence']['drift_events'].append({
                'week': self.week_number,
                'kind': 'misallocation',
            })

        state['flags']['s4_precommitted'] = False
        state['decision_history'].append({
            'week': self.week_number,
            'decision_key': 'migration_reckoning',
            'choices': p,
            'trap_flags': auto.trap_flags,
        })
        validate_run_state(state)
        return state

    def finalize_state_update(self, score_record, run_state: dict) -> dict:
        state = deepcopy(run_state)
        p = score_record.week_instance.submission.structured_payload
        flags = score_record.auto_components.get('trap_flags', [])
        plan_sound = bool(score_record.instructor_components.get('plan_sound'))
        money_thrown = p.get('migration_fate') == 'rescue' or p.get('integrator_decision') == 'take_accelerator'

        if money_thrown and not plan_sound:
            state = advance_gate(state, 'budget_credibility', to_state='closed', week=self.week_number)

        forward = p.get('migration_fate') in ('restructure', 'descope', 'kill')
        if forward and p.get('communication_posture') == 'transparent_ownership' and plan_sound:
            state['relationships']['reinhardt'] += WEEK3_REINHARDT_CONVERSION
        elif 'sunk_cost_pushthrough' in flags or 'blame_shift' in flags:
            state['relationships']['reinhardt'] -= WEEK3_REINHARDT_LOSS

        validate_run_state(state)
        return state


def _as_bool(value):
    return value is True or value in ('true', 'True', 'on', '1', 1)
