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


class RecordOutranksTheDeliverableTests(TestCase):
    """A firm that reversed and wrote that it had not was congratulated for
    continuity. The generator only ever saw the firm's own account of itself.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='rev@example.com', password='pw')
        cohort = Cohort.objects.create(name='SIM-REVERSAL', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.user)
        self.run = Run.objects.create(team=team)

    def _record(self, coherence, flags):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='Our direction has not changed; this is sequencing, not a reversal.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        record = instance.score_record
        components = record.auto_components
        components['scores'] = {**components.get('scores', {}), 'coherence': coherence}
        components['trap_flags'] = flags
        record.auto_components = components
        record.save(update_fields=['auto_components'])
        return record

    def test_a_reversal_is_given_to_the_model_as_fact(self):
        stub = _Stub(GOOD)
        generate_feedback(self._record(-2, ['coherence_drift', 'no_governance']), client=stub)
        ctx = stub.context
        self.assertIn('moving OFF the direction they set in week 1', ctx)
        self.assertIn('not supported', ctx)
        self.assertIn('did not put a governance structure in place', ctx)

    def test_holding_the_line_is_also_given(self):
        stub = _Stub(GOOD)
        generate_feedback(self._record(2, []), client=stub)
        self.assertIn('continuing the direction they set in week 1', stub.context)

    def test_the_scoring_itself_is_still_withheld(self):
        """The record reaches the model as behaviour, never as a rubric."""
        stub = _Stub(GOOD)
        generate_feedback(self._record(-2, ['coherence_drift', 'calloway_misread_safe']), client=stub)
        lowered = stub.context.lower()
        for leak in ('coherence', '-2', 'coherence_drift', 'calloway_misread_safe',
                     'trap', 'flag', 'penalty', 'score'):
            self.assertNotIn(leak, lowered, f'context leaked {leak!r}')

    def test_an_unmapped_flag_is_omitted_rather_than_guessed_at(self):
        stub = _Stub(GOOD)
        generate_feedback(self._record(0, ['some_future_flag_nobody_mapped']), client=stub)
        self.assertNotIn('some_future_flag', stub.context)
        self.assertNotIn('nobody mapped', stub.context)

    def test_the_prompt_says_the_record_wins(self):
        # Normalised: the rule is wrapped across lines in the prompt source.
        flat = ' '.join(SYSTEM_PROMPT.split())
        self.assertIn('not evidence that it is true', flat)
        self.assertIn('Never congratulate a firm for holding a line the record shows they left', flat)


class DraftFailureReportingTests(TestCase):
    """A failed draft must say why. An instructor who sees nothing saves a grade
    with no feedback, and the student screen renders nothing at all."""

    def setUp(self):
        self.user = User.objects.create_user(username='fail@example.com', password='pw')
        cohort = Cohort.objects.create(name='SIM-FAIL', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.user)
        run = Run.objects.create(team=team)
        instance = view_briefing(run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A considered current-state memo.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        self.record = instance.score_record

    def test_every_failure_path_returns_a_reason(self):
        class Boom:
            def complete(self, **_):
                raise RuntimeError('model unavailable')

        for client, expected in (
            (Boom(), 'could not be generated'),
            (_Stub('Too short.'), 'too short'),
            (_Stub(GOOD + ' Your coherence score was strong.'), 'named the scoring'),
        ):
            text, problem = generate_feedback(self.record, client=client)
            self.assertEqual(text, '')
            self.assertTrue(problem, 'a failure returned no reason at all')
            self.assertIn(expected, problem)

    def test_the_reason_does_not_name_the_words_it_rejected(self):
        """The reason is shown in the grading pane, so listing the offending
        terms put the vocabulary back on screen."""
        _, problem = generate_feedback(
            self.record, client=_Stub(GOOD + ' That gate was weighted heavily.')
        )
        self.assertNotIn('gate', problem)
        self.assertNotIn('weighted', problem)

    def test_an_overlong_draft_is_asked_once_to_cut(self):
        long_text = ' '.join(['word'] * 400)
        stub = _SeqStub([long_text, GOOD])
        text, problem = generate_feedback(self.record, client=stub)
        self.assertEqual(problem, '')
        self.assertEqual(text, GOOD)
        self.assertEqual(stub.calls, 2)

    def test_a_leak_is_not_retried(self):
        stub = _SeqStub([GOOD + ' Your score was high.', GOOD])
        text, _ = generate_feedback(self.record, client=stub)
        self.assertEqual(text, '')
        self.assertEqual(stub.calls, 1, 'a leaking draft was retried')


class _SeqStub:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, *, system, messages):
        self.calls += 1
        return self.replies[min(self.calls - 1, len(self.replies) - 1)]
