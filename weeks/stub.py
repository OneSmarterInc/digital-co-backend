from core.models import Tier
from core.state import append_decision

from .modules import WeekModule
from .structures import (
    Artifact,
    AutoScore,
    Briefing,
    DecisionField,
    DecisionSpec,
    WeekAdvisorContext,
)


class StubWeekModule(WeekModule):
    week_number = 1
    title = 'Foundation Stub Week'

    def briefing(self, tier: Tier) -> Briefing:
        signals = ['This is a foundation smoke test.']
        if tier == Tier.UNDERGRAD:
            signals.append('Undergrad tier receives more explicit planted signals.')
        return Briefing(
            title=self.title,
            body='A generic DigitalCo operating decision is required to prove the engine lifecycle.',
            exec_reads=['No real week content is implemented in Build 01.'],
            signals=signals,
        )

    def artifacts(self, tier: Tier) -> list[Artifact]:
        body = 'Generic artifact used only to verify briefing and submission flow.'
        if tier == Tier.UNDERGRAD:
            body += ' The relevant consideration is stated plainly for this tier.'
        return [Artifact(title='Stub Operating Note', body=body)]

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        return WeekAdvisorContext(
            facts=['The team is making a generic operating decision.', 'No week-specific facts exist yet.'],
            stance='Probe tradeoffs without revealing an optimal answer.',
            signal='Keep the decision aligned with accumulated state.',
            misdirection='Do not introduce real Week 1 content.',
        )

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        return DecisionSpec(
            fields=[
                DecisionField(
                    key='operating_choice',
                    label='Operating choice',
                    choices=[
                        {'value': 'balanced', 'label': 'Balanced investment'},
                        {'value': 'speed_only', 'label': 'Speed only'},
                    ],
                    trap_choices=['speed_only'],
                )
            ],
            deliverable_prompt='Explain the rationale for the generic operating choice.',
            rubric_variant='undergrad' if tier == Tier.UNDERGRAD else 'graduate',
        )

    def score_auto(self, submission, run_state: dict) -> AutoScore:
        choice = submission.structured_payload.get('operating_choice')
        if choice == 'speed_only':
            return AutoScore(
                scores={'strategic_judgment': 1, 'execution_consequence': 0},
                trap_flags=['speed_without_controls'],
                components={'operating_choice': choice},
            )
        return AutoScore(
            scores={'strategic_judgment': 2, 'execution_consequence': 2},
            components={'operating_choice': choice},
        )

    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        return append_decision(
            run_state,
            week=self.week_number,
            decision_key='operating_choice',
            choice=submission.structured_payload.get('operating_choice'),
            trap_flags=auto.trap_flags,
        )
