"""The deliverable-quality proposal.

The scale and the plumbing matter, but the constraint is the thing: this must
judge how the document is built, never whether it agrees with the decision. If
it drifts into judging the decision, deliverable quality becomes a second copy
of strategic judgment and the four dimensions become three.
"""
from django.test import TestCase

from core.models import Cohort, Run, Team, Tier, User
from engine.services import submit_week, view_briefing
from feedback.quality import (
    GRADUATE_STANDARD, MAX_SCORE, MIN_SCORE, SYSTEM_PROMPT, UNDERGRAD_STANDARD,
    build_context, parse, propose_quality,
)
from weeks.tests import week1_payload


class _Stub:
    def __init__(self, reply):
        self.reply = reply
        self.context = None
        self.calls = 0

    def complete(self, *, system, messages):
        self.calls += 1
        self.context = messages[0]['content']
        return self.reply


class ParsingTests(TestCase):
    def test_a_well_formed_reply_parses(self):
        score, why, problem = parse('SCORE: 2\nWHY: Names its numbers and its trade-offs.')
        self.assertEqual(score, 2)
        self.assertEqual(problem, '')
        self.assertIn('trade-offs', why)

    def test_a_score_outside_the_band_is_refused(self):
        for bad in (MAX_SCORE + 1, MIN_SCORE - 1, 10):
            score, _, problem = parse(f'SCORE: {bad}\nWHY: x')
            self.assertIsNone(score, f'{bad} was accepted')
            self.assertIn('outside', problem)

    def test_prose_with_no_score_is_refused(self):
        score, _, problem = parse('This deliverable was quite good really.')
        self.assertIsNone(score)
        self.assertIn('no score', problem)


class ConstraintTests(TestCase):
    def test_the_prompt_separates_the_artifact_from_the_decision(self):
        self.assertIn('not the decision it argues for', SYSTEM_PROMPT)
        self.assertIn('you think is wrong scores WELL', SYSTEM_PROMPT)
        self.assertIn('you think is right scores BADLY', SYSTEM_PROMPT)

    def test_the_band_is_narrower_than_the_other_dimensions(self):
        self.assertEqual((MIN_SCORE, MAX_SCORE), (-1, 3))


class GenerationTests(TestCase):
    def _record(self, tier):
        user = User.objects.create_user(username=f'dq-{tier}@example.com', password='pw')
        cohort = Cohort.objects.create(name=f'SIM-DQ-{tier}', tier=tier)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(user)
        run = Run.objects.create(team=team)
        instance = view_briefing(run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo naming the numbers and the trade-offs.',
            submitted_by=user,
        )
        instance.refresh_from_db()
        return instance.score_record

    def test_the_tier_changes_the_standard_the_model_is_given(self):
        under = _Stub('SCORE: 2\nWHY: ok')
        propose_quality(self._record(Tier.UNDERGRAD), client=under)
        self.assertIn('named frameworks appropriate to the question', under.context)
        self.assertNotIn('framework scaffolding', under.context)

        grad = _Stub('SCORE: 2\nWHY: ok')
        propose_quality(self._record(Tier.GRADUATE), client=grad)
        self.assertIn('without leaning on framework scaffolding', grad.context)
        self.assertNotIn('named frameworks appropriate', grad.context)

    def test_the_model_never_sees_how_the_decision_scored(self):
        stub = _Stub('SCORE: 2\nWHY: ok')
        propose_quality(self._record(Tier.UNDERGRAD), client=stub)
        lowered = stub.context.lower()
        for leak in ('strategic judgment', 'execution consequence', 'coherence',
                     'trap', 'auto_components', 'penalty'):
            self.assertNotIn(leak, lowered, f'context leaked {leak!r}')

    def test_a_failure_proposes_zero_rather_than_raising(self):
        class Boom:
            def complete(self, **_):
                raise RuntimeError('model down')

        value, _, problem = propose_quality(self._record(Tier.UNDERGRAD), client=Boom())
        self.assertEqual(value, 0)
        self.assertIn('could not be generated', problem)

    def test_a_submission_with_no_writing_is_not_sent_to_the_model(self):
        record = self._record(Tier.UNDERGRAD)
        record.week_instance.submission.deliverable_text = ''
        record.week_instance.submission.save(update_fields=['deliverable_text'])
        stub = _Stub('SCORE: 3\nWHY: ok')
        value, _, problem = propose_quality(record, client=stub)
        self.assertEqual(value, 0)
        self.assertEqual(stub.calls, 0)
        self.assertIn('no written deliverable', problem)


class RecordingTests(TestCase):
    """The proposal is logged in full alongside the number, so it can be
    compared against the instructor's judgement before being trusted."""

    def test_the_proposal_and_its_reasoning_are_stored(self):
        from unittest.mock import patch

        user = User.objects.create_user(username='dq-log@example.com', password='pw')
        cohort = Cohort.objects.create(name='SIM-DQ-LOG', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(user)
        run = Run.objects.create(team=team)
        instance = view_briefing(run)

        with patch('feedback.quality.get_llm_client',
                   return_value=_Stub('SCORE: 2\nWHY: Names its numbers.')):
            submit_week(
                instance,
                structured_payload=week1_payload(),
                deliverable_text='A memo with figures and stated trade-offs.',
                submitted_by=user,
            )
        instance.refresh_from_db()
        record = instance.score_record
        proposal = record.auto_components['deliverable_quality_proposal']
        self.assertEqual(proposal['score'], 2)
        self.assertIn('Names its numbers', proposal['why'])
        self.assertEqual(record.deliverable_quality, 2)
        self.assertEqual(record.auto_components['scores']['deliverable_quality'], 2)

    def test_a_dead_model_leaves_the_record_gradeable(self):
        from unittest.mock import patch

        user = User.objects.create_user(username='dq-dead@example.com', password='pw')
        cohort = Cohort.objects.create(name='SIM-DQ-DEAD', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(user)
        run = Run.objects.create(team=team)
        instance = view_briefing(run)

        with patch('feedback.quality.get_llm_client', side_effect=RuntimeError('down')):
            submit_week(
                instance,
                structured_payload=week1_payload(),
                deliverable_text='A memo.',
                submitted_by=user,
            )
        instance.refresh_from_db()
        self.assertEqual(instance.score_record.deliverable_quality, 0)
        self.assertIn(
            'could not be generated',
            instance.score_record.auto_components['deliverable_quality_proposal']['problem'],
        )
