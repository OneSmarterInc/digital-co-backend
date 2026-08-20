"""The preamble is generated without a human in the loop and read immediately,
so the guards are the whole safety story: it must not name the scoring, must not
tell a firm what to decide, and must never break a briefing when it fails.
"""
from django.test import TestCase

from briefing.prompts import SYSTEM_PROMPT, is_usable
from briefing.services import build_context, ensure_preamble, generate_preamble
from core.models import Cohort, Run, Team, Tier, User
from engine.services import view_briefing

GOOD = (
    "You came into this quarter having told the board that the data platform comes "
    "before the ERP, and you have held that line for two rounds running. It has cost "
    "you the finance team's goodwill and the programme date you originally promised. "
    "That is the position you are standing on this morning."
)


class _Stub:
    def __init__(self, reply):
        self.reply = reply
        self.context = None
        self.calls = 0

    def complete(self, *, system, messages):
        self.calls += 1
        self.context = messages[0]['content']
        return self.reply


class _Boom:
    def complete(self, **_):
        raise RuntimeError('model unavailable')


class UsabilityTests(TestCase):
    def test_a_good_preamble_passes(self):
        ok, problem = is_usable(GOOD)
        self.assertTrue(ok, problem)

    def test_naming_the_scoring_is_refused(self):
        for term in ('coherence', 'your score', 'the rubric', 'a trap', 'the standings'):
            ok, problem = is_usable(GOOD + f' Watch {term} here.')
            self.assertFalse(ok, f'{term!r} was allowed through')
            self.assertIn('scoring machinery', problem)

    def test_advice_is_refused(self):
        ok, problem = is_usable(GOOD + ' You should descope the programme now.')
        self.assertFalse(ok)
        self.assertIn('what to decide', problem)

    def test_length_bounds(self):
        self.assertFalse(is_usable('You held your line.')[0])
        self.assertFalse(is_usable(' '.join(['word'] * 200))[0])

    def test_the_prompt_forbids_advising_and_the_dimension_names(self):
        lowered = SYSTEM_PROMPT.lower()
        for term in ('coherence', 'traps', 'rankings'):
            self.assertIn(term, lowered)
        self.assertIn('Never say what they should decide', SYSTEM_PROMPT)


class GenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pre-student', password='pw')
        cohort = Cohort.objects.create(name='SIM-PRE', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(self.user)
        self.run = Run.objects.create(team=team)

    def _with_history(self, week=4):
        self.run.current_week = week
        # Merge, never replace: Run.state validates against a required schema.
        self.run.state = {
            **self.run.state,
            'coherence_anchor': 'Data platform before ERP, and we accept the delay.',
            'decision_history': [
                {'week': 1, 'choices': {'posture': 'consolidate'}},
                {'week': 2, 'choices': {'vendor': 'hold'}},
            ],
        }
        self.run.save()

    def test_round_one_never_gets_one(self):
        text, problem = generate_preamble(self.run, 1, client=_Stub(GOOD))
        self.assertEqual(text, '')
        self.assertIn('round 1', problem)

    def test_a_firm_with_no_history_gets_none(self):
        stub = _Stub(GOOD)
        text, problem = generate_preamble(self.run, 3, client=stub)
        self.assertEqual(text, '')
        # Never asked, so it cannot invent continuity that does not exist.
        self.assertEqual(stub.calls, 0)

    def test_the_model_sees_the_firms_history_and_no_scoring(self):
        self._with_history()
        stub = _Stub(GOOD)
        generate_preamble(self.run, 4, client=stub)
        self.assertIn('round 4 of fourteen', stub.context)
        self.assertIn('Data platform before ERP', stub.context)
        for term in ('coherence', 'rubric', 'trap', 'score'):
            self.assertNotIn(term, stub.context.lower(), f'context leaked {term!r}')

    def test_drifting_output_is_discarded(self):
        self._with_history()
        text, problem = generate_preamble(
            self.run, 4, client=_Stub(GOOD + ' Your coherence score is at risk.')
        )
        self.assertEqual(text, '')
        self.assertIn('scoring machinery', problem)

    def test_a_failure_is_not_an_exception(self):
        self._with_history()
        text, problem = generate_preamble(self.run, 4, client=_Boom())
        self.assertEqual(text, '')
        self.assertIn('could not be generated', problem)


class EnsureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pre-ensure', password='pw')
        cohort = Cohort.objects.create(name='SIM-ENS', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        team.members.add(self.user)
        self.run = Run.objects.create(team=team, current_week=4)
        self.run.state = {
            **self.run.state,
            'coherence_anchor': 'Data platform before ERP, and we accept the delay.',
            'decision_history': [{'week': 1, 'choices': {'posture': 'consolidate'}}],
        }
        self.run.save()
        from weeks.models import WeekInstance, WeekInstanceStatus
        self.instance = WeekInstance.objects.create(
            run=self.run, week_number=4, status=WeekInstanceStatus.BRIEFING
        )

    def test_it_is_written_once_and_reused(self):
        stub = _Stub(GOOD)
        first = ensure_preamble(self.instance, client=stub)
        self.assertEqual(first, GOOD)
        # Every member of the firm must read the same words.
        second = ensure_preamble(self.instance, client=_Stub('Completely different text here now.'))
        self.assertEqual(second, GOOD)
        self.assertEqual(stub.calls, 1)

    def test_a_failed_attempt_is_not_retried_on_every_load(self):
        ensure_preamble(self.instance, client=_Boom())
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.preamble, '')
        self.assertIn('could not be generated', self.instance.preamble_problem)
        stub = _Stub(GOOD)
        self.assertEqual(ensure_preamble(self.instance, client=stub), '')
        self.assertEqual(stub.calls, 0)

    def test_opening_a_briefing_never_fails_on_a_broken_model(self):
        from unittest.mock import patch
        with patch('briefing.services.get_llm_client', side_effect=RuntimeError('down')):
            instance = view_briefing(self.run)
        self.assertEqual(instance.preamble, '')
        from weeks.models import WeekInstanceStatus
        self.assertEqual(instance.status, WeekInstanceStatus.CONSULTATION)
