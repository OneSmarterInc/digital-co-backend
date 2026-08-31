"""The preamble is generated without a human in the loop and read immediately,
so the guards are the whole safety story: it must not name the scoring, must not
tell a firm what to decide, and must never break a briefing when it fails.
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from api.views import RunView

from briefing.prompts import MAX_WORDS, SYSTEM_PROMPT, is_usable
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


class PerPageLoadTests(TestCase):
    """Every student in a firm must read identical text, and it must not change
    between readings. That means the preamble is written once when the round
    opens and stored — never regenerated when a page is loaded.
    """

    def setUp(self):
        cohort = Cohort.objects.create(name='SIM-LOAD', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        self.a = User.objects.create_user(username='load-a@example.com', password='pw')
        self.b = User.objects.create_user(username='load-b@example.com', password='pw')
        team.members.add(self.a, self.b)
        self.run = Run.objects.create(team=team, current_week=4)
        self.run.state = {
            **self.run.state,
            'coherence_anchor': 'Data platform before ERP, and we accept the delay.',
            'decision_history': [{'week': 1, 'choices': {'posture': 'consolidate'}}],
        }
        self.run.save()

    def test_the_model_is_called_once_no_matter_how_many_times_it_is_read(self):
        stub = _Stub(GOOD)
        with patch('briefing.services.get_llm_client', return_value=stub):
            first = view_briefing(self.run)
            # Every subsequent open of the same round, by anyone in the firm.
            for _ in range(4):
                view_briefing(self.run)
        self.assertEqual(stub.calls, 1)
        self.assertEqual(first.preamble, GOOD)

    def test_two_students_in_the_same_firm_read_the_same_words(self):
        with patch('briefing.services.get_llm_client', return_value=_Stub(GOOD)):
            view_briefing(self.run)

        seen = set()
        for student in (self.a, self.b):
            request = APIRequestFactory().get('/api/run/')
            force_authenticate(request, user=student)
            resp = RunView.as_view()(request)
            self.assertEqual(resp.status_code, 200)
            seen.add(resp.data['briefing']['preamble'])
        self.assertEqual(seen, {GOOD})

    def test_the_stored_text_survives_a_model_that_later_answers_differently(self):
        with patch('briefing.services.get_llm_client', return_value=_Stub(GOOD)):
            view_briefing(self.run)
        drifted = _Stub('You are carrying something else entirely into this round now.')
        with patch('briefing.services.get_llm_client', return_value=drifted):
            again = view_briefing(self.run)
        self.assertEqual(again.preamble, GOOD)
        self.assertEqual(drifted.calls, 0)

    def test_round_one_stores_no_preamble_and_never_asks(self):
        run = Run.objects.create(
            team=Team.objects.create(
                cohort=Cohort.objects.get(name='SIM-LOAD'), name='Team B',
            ),
        )
        stub = _Stub(GOOD)
        with patch('briefing.services.get_llm_client', return_value=stub):
            instance = view_briefing(run)
        self.assertEqual(instance.preamble, '')
        self.assertEqual(stub.calls, 0)


class LengthRetryTests(TestCase):
    """A preamble that runs long is worth a second ask; one that leaks is not.

    Overshooting the word limit is the common failure — the model writes
    something perfectly good and goes over — and discarding it outright is why a
    live backfill reported "too long for an opening" and wrote nothing. Naming
    the scoring is a different failure, and retrying that just samples until one
    slips through.
    """

    def setUp(self):
        cohort = Cohort.objects.create(name='SIM-RETRY', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        user = User.objects.create_user(username='retry@example.com', password='pw')
        team.members.add(user)
        self.run = Run.objects.create(team=team, current_week=4)
        self.run.state = {
            **self.run.state,
            'coherence_anchor': 'Data platform before ERP, and we accept the delay.',
            'decision_history': [{'week': 1, 'choices': {'posture': 'consolidate'}}],
        }
        self.run.save()

    def test_an_overlong_reply_is_asked_once_to_cut(self):
        long_text = ' '.join(['word'] * (MAX_WORDS + 30))
        stub = _SequenceStub([long_text, GOOD])
        text, problem = generate_preamble(self.run, 4, client=stub)
        self.assertEqual(problem, '')
        self.assertEqual(text, GOOD)
        self.assertEqual(stub.calls, 2)
        self.assertIn('hard limit', stub.last_messages[-1]['content'])

    def test_it_gives_up_after_one_retry(self):
        long_text = ' '.join(['word'] * (MAX_WORDS + 30))
        stub = _SequenceStub([long_text, long_text])
        text, problem = generate_preamble(self.run, 4, client=stub)
        self.assertEqual(text, '')
        self.assertIn('too long', problem)
        self.assertEqual(stub.calls, 2, 'retried more than once')

    def test_a_leak_is_discarded_without_a_retry(self):
        leaky = GOOD + ' Your coherence score is at risk.'
        stub = _SequenceStub([leaky, GOOD])
        text, problem = generate_preamble(self.run, 4, client=stub)
        self.assertEqual(text, '')
        self.assertIn('scoring machinery', problem)
        self.assertEqual(stub.calls, 1, 'a leaking reply was retried')

    def test_the_prompt_states_the_budget_the_guard_enforces(self):
        self.assertIn('no more than 65 words', SYSTEM_PROMPT)
        self.assertLess(65, MAX_WORDS, 'the prompt asks for more than the guard allows')


class _SequenceStub:
    """Returns each reply in turn, so a retry can be observed."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.last_messages = None

    def complete(self, *, system, messages):
        self.calls += 1
        self.last_messages = messages
        return self.replies[min(self.calls - 1, len(self.replies) - 1)]


class HouseStyleTests(TestCase):
    """The product is written S/4 everywhere a team reads. A second spelling
    reads as a second system, and the model writes "S4" often enough that
    asking it not to is not sufficient on its own."""

    def test_generated_text_is_normalised(self):
        from briefing.services import house_style

        self.assertEqual(house_style('We kept the S4 mapped.'), 'We kept the S/4 mapped.')
        self.assertEqual(house_style('S4HANA is half-migrated.'), 'S/4HANA is half-migrated.')

    def test_it_leaves_correct_text_alone(self):
        from briefing.services import house_style

        for text in ('Your S/4 work is unchanged.', 'S/4HANA sits beside it.'):
            self.assertEqual(house_style(text), text)

    def test_it_does_not_touch_things_that_merely_look_similar(self):
        """`s4_disposition` is a field key, and S40 is a different number."""
        from briefing.services import house_style

        self.assertEqual(house_style('The s4_disposition key.'), 'The s4_disposition key.')
        self.assertEqual(house_style('S40 units shipped.'), 'S40 units shipped.')

    def test_a_preamble_is_normalised_on_the_way_out(self):
        from unittest.mock import patch

        cohort = Cohort.objects.create(name='SIM-HOUSE', tier=Tier.UNDERGRAD)
        team = Team.objects.create(cohort=cohort, name='Team A')
        user = User.objects.create_user(username='house@example.com', password='pw')
        team.members.add(user)
        run = Run.objects.create(team=team, current_week=4)
        run.state = {
            **run.state,
            'coherence_anchor': 'Data platform before ERP, and we accept the delay.',
            'decision_history': [{'week': 1, 'choices': {'posture': 'consolidate'}}],
        }
        run.save()

        drafted = GOOD.replace('the programme', 'the S4 programme')
        with patch('briefing.services.get_llm_client', return_value=_Stub(drafted)):
            text, problem = generate_preamble(run, 4)
        self.assertEqual(problem, '')
        self.assertNotIn('S4 ', text)
        self.assertIn('S/4', text)
