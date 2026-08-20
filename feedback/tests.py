"""Guarding the constraints, not the prose.

The rules that matter — never name the scoring, never say what to decide, never
compare firms — are enforced by is_usable() after generation, so a drifting
model produces no feedback rather than damaging feedback. These test that
enforcement, and that the model is never shown a rubric or a later week.
"""
from django.test import TestCase

from core.models import Cohort, Run, Team, Tier, User
from engine.services import submit_week, view_briefing
from feedback.prompts import PROHIBITED, SYSTEM_PROMPT, is_usable
from feedback.services import build_context, generate_feedback
from weeks.tests import week1_payload

GOOD = (
    "Your anchor rules something out and says so plainly — the programme will not be "
    "completed as scoped, and you named who that upsets. That is what makes a position "
    "usable later: when two things compete for the same money, this sentence decides it. "
    "You committed to service revenue as the future without saying what would tell you it "
    "was working, or by when. A board that funds this will ask what changes in six months, "
    "and right now the statement has no answer. You have told this company that data comes "
    "before the ERP, and holding that will be harder in a week where the cost of holding it "
    "is visible on the page."
)


class _Stub:
    def __init__(self, reply):
        self.reply = reply
        self.system = None
        self.context = None

    def complete(self, *, system, messages):
        self.system = system
        self.context = messages[0]['content']
        return self.reply


class UsabilityTests(TestCase):
    def test_good_feedback_passes(self):
        ok, problem = is_usable(GOOD)
        self.assertTrue(ok, problem)

    def test_anything_naming_the_scoring_is_refused(self):
        for term in ('coherence', 'strategic judgment', 'you lost points', 'the rubric',
                     'your score', 'a trap', 'the gate', 'ranked'):
            text = GOOD + f' Also, {term} mattered here.'
            ok, problem = is_usable(text)
            self.assertFalse(ok, f'{term!r} was allowed through')
            self.assertIn('scoring', problem)

    def test_comparisons_with_other_teams_are_refused(self):
        ok, _ = is_usable(GOOD + ' Other teams did better on this.')
        self.assertFalse(ok)

    def test_too_short_is_refused(self):
        ok, problem = is_usable('Good work.')
        self.assertFalse(ok)
        self.assertIn('too short', problem)

    def test_the_prompt_forbids_the_dimension_names(self):
        for term in ('strategic judgment', 'execution consequence', 'coherence',
                     'deliverable quality'):
            self.assertIn(term, SYSTEM_PROMPT.lower())  # named, in order to forbid them
        self.assertIn('Never mention scores', SYSTEM_PROMPT)
        self.assertIn('Never tell them what to decide', SYSTEM_PROMPT)


class GenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fb-student', password='pw')
        cohort = Cohort.objects.create(name='SIM-FB', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(self.user)
        self.run = Run.objects.create(team=team)
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        self.record = instance.score_record

    def test_usable_output_is_returned(self):
        stub = _Stub(GOOD)
        text, problem = generate_feedback(self.record, client=stub)
        self.assertEqual(problem, '')
        self.assertEqual(text, GOOD)

    def test_the_model_is_shown_what_they_wrote_and_no_rubric(self):
        stub = _Stub(GOOD)
        generate_feedback(self.record, client=stub)
        context = stub.context.lower()
        self.assertIn('round 1 of fourteen', context)
        self.assertIn('what they wrote this round', context)
        # It must not be able to leak what it was never given.
        for term in ('strategic judgment', 'execution consequence', 'deliverable quality',
                     'rubric', 'trap', 'auto_scores'):
            self.assertNotIn(term, context, f'context leaked {term!r}')

    def test_drifting_output_is_discarded_rather_than_shown(self):
        text, problem = generate_feedback(self.record, client=_Stub(GOOD + ' Your coherence was strong.'))
        self.assertEqual(text, '')
        self.assertIn('scoring', problem)

    def test_generic_output_is_discarded(self):
        text, problem = generate_feedback(self.record, client=_Stub('Strong work overall. Keep it up.'))
        self.assertEqual(text, '')
        self.assertIn('too short', problem)

    def test_a_generation_failure_is_not_an_exception(self):
        class Boom:
            def complete(self, **_):
                raise RuntimeError('model unavailable')

        text, problem = generate_feedback(self.record, client=Boom())
        self.assertEqual(text, '')
        self.assertIn('could not be generated', problem)
