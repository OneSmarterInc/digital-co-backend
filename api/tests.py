"""Multi-simulation run resolution.

A student can be enrolled in several simulations at once — one Team + Run per
cohort. These tests pin the behavior that keeps those enrollments independent:
run resolution must be scoped to the cohort the request targets, not collapse
onto an arbitrary Run.first(). Regression guard for the bug where every student
runtime endpoint served whichever run happened to come back first.
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from django.db.models import Count, Sum

from advisors.models import (
    BILLED, AdvisorDefinition, AdvisorSession, Conversation, GroupSession,
)
from core.models import (
    DEFAULT_ADVISOR_HOURLY_RATE, Cohort, Enrollment, Invitation, Run, Team, Tier, User, UserRole,
)
from core.state import SCORE_DIMENSIONS
from engine.services import submit_week, view_briefing
from scoring.services import finalize_score
from weeks.tests import week1_payload
from scoring.models import ScoreRecord
from weeks.models import Submission, WeekInstance, WeekInstanceStatus

from .instructor_api import (
    InstructorCoFacultyDetailView, InstructorCoFacultyView,
    InstructorFirmDetailView, InstructorFirmsView, InstructorMoveEnrollmentView,
    InstructorSimulationDetailView, _advisor_usage_by_student, _billing,
)
from .student_api import StudentPerformanceView
from .views import (
    AdminFacultyView, AdminSimulationsView, GroupConversationView, InstructorFeedbackDraftView,
    InstructorQueueView, InstructorScoreView, RunView, resolve_run, run_for_user,
)


class MultiSimRunResolutionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='multi@example.com', password='pw', role=UserRole.STUDENT,
        )
        # Two independent simulations the same student belongs to.
        self.cohort_a = Cohort.objects.create(name='SIM-A', tier=Tier.UNDERGRAD)
        self.cohort_b = Cohort.objects.create(name='SIM-B', tier=Tier.GRADUATE)
        self.run_a = self._enroll(self.cohort_a, current_week=3)
        self.run_b = self._enroll(self.cohort_b, current_week=7)

    def _enroll(self, cohort, *, current_week):
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.student)
        return Run.objects.create(team=team, current_week=current_week)

    def _drf_get(self, query=''):
        request = Request(APIRequestFactory().get(f'/api/run/{query}'))
        request.user = self.student
        return request

    def test_run_for_user_scopes_to_cohort(self):
        self.assertEqual(run_for_user(self.student, self.cohort_a.id), self.run_a)
        self.assertEqual(run_for_user(self.student, self.cohort_b.id), self.run_b)

    def test_resolve_run_reads_cohort_query_param(self):
        self.assertEqual(resolve_run(self._drf_get(f'?cohort={self.cohort_a.id}')), self.run_a)
        self.assertEqual(resolve_run(self._drf_get(f'?cohort={self.cohort_b.id}')), self.run_b)

    def test_resolve_run_falls_back_without_cohort(self):
        # Single-sim behavior is preserved: absent a cohort, resolve to a run.
        self.assertIn(resolve_run(self._drf_get()), {self.run_a, self.run_b})

    def test_invalid_cohort_resolves_to_no_run(self):
        self.assertIsNone(resolve_run(self._drf_get('?cohort=abc')))
        # A cohort the student isn't in also yields nothing, not another sim's run.
        other = Cohort.objects.create(name='SIM-C', tier=Tier.UNDERGRAD)
        self.assertIsNone(run_for_user(self.student, other.id))

    def test_run_view_returns_the_requested_cohorts_run(self):
        view = RunView.as_view()
        for cohort, run in ((self.cohort_a, self.run_a), (self.cohort_b, self.run_b)):
            request = APIRequestFactory().get(f'/api/run/?cohort={cohort.id}')
            force_authenticate(request, user=self.student)
            response = view(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['run']['id'], run.id)
            self.assertEqual(response.data['run']['current_week'], run.current_week)


class InstructorGradingQueueTests(TestCase):
    """The grading queue must serialize a submitted week without crashing, and
    scope to one simulation when asked. Regression guard for score_record_json
    reading the non-existent `.submissions` (which 500-ed the whole queue the
    moment any week was submitted) and for cross-sim bleed on ?cohort=."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='prof@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.ug = self._sim('SIM-UG', Tier.UNDERGRAD, 'Team 1')
        self.grad = self._sim('SIM-GRAD', Tier.GRADUATE, 'Team 2')

    def _sim(self, name, tier, team_name):
        cohort = Cohort.objects.create(name=name, tier=tier)
        cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=cohort, name=team_name)
        run = Run.objects.create(team=team, current_week=1)
        instance = WeekInstance.objects.create(
            run=run, week_number=1, status=WeekInstanceStatus.SUBMITTED,
        )
        submission = Submission.objects.create(
            week_instance=instance, structured_payload={'x': 1}, deliverable_text='done',
        )
        instance.submission = submission
        instance.save(update_fields=['submission'])
        ScoreRecord.objects.create(week_instance=instance, auto_components={'scores': {}})
        return {'cohort': cohort, 'run': run}

    def _queue(self, query=''):
        request = APIRequestFactory().get(f'/api/instructor/queue/{query}')
        force_authenticate(request, user=self.instructor)
        return InstructorQueueView.as_view()(request)

    def test_queue_serializes_submitted_week_without_crashing(self):
        resp = self._queue('?ungraded=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        row = next(r for r in resp.data if r['cohort'] == 'SIM-UG')
        self.assertEqual(row['deliverable_text'], 'done')
        self.assertEqual(row['decisions'], {'x': 1})

    def test_queue_scopes_to_one_cohort(self):
        resp = self._queue(f"?cohort={self.ug['cohort'].id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({r['cohort'] for r in resp.data}, {'SIM-UG'})


class GroupRoomBillingTests(TestCase):
    """A war-room hour is not free: it costs the cohort's hourly rate once per
    advisor seated in the room, on the same one-started-hour meter as a 1:1.
    """

    def setUp(self):
        self.student = User.objects.create_user(
            username='room@example.com', password='pw', role=UserRole.STUDENT,
        )
        self.cohort = Cohort.objects.create(
            name='SIM-ROOM', tier=Tier.UNDERGRAD, advisor_hourly_rate=100,
        )
        team = Team.objects.create(cohort=self.cohort, name='Team 1')
        team.members.add(self.student)
        self.enrollment = Enrollment.objects.create(
            cohort=self.cohort, student=self.student, team=team,
        )
        self.run = Run.objects.create(team=team, current_week=1)

    def _room(self, advisors):
        return GroupSession.objects.create(
            run=self.run, week_number=1, active_advisors=advisors,
        )

    def _meter(self, session):
        return GroupConversationView._meter_group_session(self.student, self.run, session)

    def test_room_hour_bills_rate_times_advisors(self):
        billed = self._meter(self._room(['a', 'b', 'c']))
        self.assertEqual(billed.hourly_rate, 100)
        self.assertEqual(billed.advisor_count, 3)
        self.assertEqual(billed.billed, 300)

    def test_second_message_inside_the_hour_rides_along(self):
        room = self._room(['a', 'b'])
        first = self._meter(room)
        second = self._meter(room)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AdvisorSession.objects.filter(group_session=room).count(), 1)

    def test_cohort_totals_include_room_hours(self):
        self._meter(self._room(['a', 'b', 'c', 'd']))
        usage = (
            AdvisorSession.objects
            .for_cohort(self.cohort)
            .filter(student=self.student)
            .aggregate(hours=Count('id'), due=Sum(BILLED))
        )
        self.assertEqual(usage['hours'], 1)
        self.assertEqual(usage['due'], 400)

    def test_faculty_totals_split_group_out_of_the_advisor_total(self):
        # One 3-advisor room hour (300) plus one 1:1 hour (100).
        self._meter(self._room(['a', 'b', 'c']))
        AdvisorSession.objects.create(
            conversation=Conversation.objects.create(
                run=self.run, week_number=1,
                advisor=AdvisorDefinition.objects.create(key='solo_a', name='A', title='t', persona='p', lane='l'),
            ),
            student=self.student, enrollment=self.enrollment, hourly_rate=100,
        )

        usage = _advisor_usage_by_student(self.cohort)[self.student.id]
        self.assertEqual((usage['hours'], usage['due']), (2, 400))
        self.assertEqual((usage['group_hours'], usage['group_due']), (1, 300))

        billing = _billing(self.cohort, [self.enrollment])
        self.assertEqual((billing['advisor_hours'], billing['advisor_billed']), (2, 400))
        self.assertEqual((billing['group_hours'], billing['group_billed']), (1, 300))


class AdvisorRateEditTests(TestCase):
    """Faculty can re-price advisor time after provisioning. Hours already billed
    keep the rate snapshotted on their session, so an edit never rewrites history.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='prof2@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            username='rate@example.com', password='pw', role=UserRole.STUDENT,
        )
        self.cohort = Cohort.objects.create(
            name='SIM-RATE', tier=Tier.UNDERGRAD, advisor_hourly_rate=100,
        )
        self.cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=self.cohort, name='Team 1')
        team.members.add(self.student)
        self.enrollment = Enrollment.objects.create(
            cohort=self.cohort, student=self.student, team=team,
        )
        self.run = Run.objects.create(team=team, current_week=1)

    def _patch(self, body, user=None):
        request = APIRequestFactory().patch(
            f'/api/instructor/simulations/{self.cohort.id}/', body, format='json',
        )
        force_authenticate(request, user=user or self.instructor)
        return InstructorSimulationDetailView.as_view()(request, cohort_id=self.cohort.id)

    def test_instructor_can_change_the_rate(self):
        resp = self._patch({'advisor_hourly_rate': 250})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['advisor_hourly_rate'], 250)
        self.assertEqual(resp.data['previous_advisor_hourly_rate'], 100)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.advisor_hourly_rate, 250)

    def test_rate_can_be_switched_on_from_zero(self):
        self.cohort.advisor_hourly_rate = 0
        self.cohort.save(update_fields=['advisor_hourly_rate'])
        self.assertEqual(self._patch({'advisor_hourly_rate': 80}).status_code, 200)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.advisor_hourly_rate, 80)

    def test_already_billed_hours_keep_their_old_rate(self):
        room = GroupSession.objects.create(
            run=self.run, week_number=1, active_advisors=['a', 'b'],
        )
        billed = GroupConversationView._meter_group_session(self.student, self.run, room)
        self._patch({'advisor_hourly_rate': 900})
        billed.refresh_from_db()
        self.assertEqual(billed.hourly_rate, 100)
        self.assertEqual(billed.billed, 200)

    def test_rejects_junk_and_out_of_range(self):
        for body in ({'advisor_hourly_rate': 'free'}, {'advisor_hourly_rate': -5},
                     {'advisor_hourly_rate': 100001}, {}):
            self.assertEqual(self._patch(body).status_code, 400)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.advisor_hourly_rate, 100)

    def test_another_instructors_cohort_is_not_editable(self):
        outsider = User.objects.create_user(
            username='other@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.assertEqual(self._patch({'advisor_hourly_rate': 1}, user=outsider).status_code, 404)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.advisor_hourly_rate, 100)


class InstructorScoreEndpointTests(TestCase):
    """The wire path the grading modal actually uses. Posting a zero adjustment
    must record the engine's proposal, not double it.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='grader@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            username='graded@example.com', password='pw', role=UserRole.STUDENT,
        )
        cohort = Cohort.objects.create(name='SIM-SCORE', tier=Tier.UNDERGRAD)
        cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.student)
        self.run = Run.objects.create(team=team)

    def test_zero_adjustment_posts_the_engine_score_unchanged(self):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.student,
        )
        instance.refresh_from_db()
        record = instance.score_record
        auto = dict(record.auto_components['scores'])
        self.assertTrue(any(auto.get(d) for d in SCORE_DIMENSIONS))

        request = APIRequestFactory().post(
            f'/api/instructor/score/{record.id}/',
            {'scores': {d: 0 for d in SCORE_DIMENSIONS}, 'anchor_strength': 'adequate'},
            format='json',
        )
        force_authenticate(request, user=self.instructor)
        resp = InstructorScoreView.as_view()(request, score_id=record.id)
        self.assertEqual(resp.status_code, 200)

        record.refresh_from_db()
        for dimension in SCORE_DIMENSIONS:
            self.assertEqual(getattr(record, dimension), auto.get(dimension, 0))


class GradingSurvivesMissingFeedbackTests(TestCase):
    """A failed model call must never block grading.

    Feedback is generated by an LLM, and an LLM is the least reliable thing in
    the request. If a draft cannot be produced — or the instructor deletes it —
    the grade still has to save, because the grade is the thing the course
    actually depends on.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='nofb-grader@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            username='nofb-student@example.com', password='pw', role=UserRole.STUDENT,
        )
        cohort = Cohort.objects.create(name='SIM-NOFB', tier=Tier.UNDERGRAD)
        cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.student)
        self.run = Run.objects.create(team=team)

    def _record(self):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.student,
        )
        instance.refresh_from_db()
        return instance.score_record

    def _post(self, record, body):
        request = APIRequestFactory().post(
            f'/api/instructor/score/{record.id}/', body, format='json',
        )
        force_authenticate(request, user=self.instructor)
        return InstructorScoreView.as_view()(request, score_id=record.id)

    def test_a_grade_saves_with_no_feedback_field_at_all(self):
        record = self._record()
        resp = self._post(record, {
            'scores': {d: 0 for d in SCORE_DIMENSIONS}, 'anchor_strength': 'adequate',
        })
        self.assertEqual(resp.status_code, 200)
        record.refresh_from_db()
        self.assertIsNotNone(record.graded_at)

    def test_a_grade_saves_when_the_instructor_deletes_the_draft(self):
        record = self._record()
        resp = self._post(record, {
            'scores': {d: 0 for d in SCORE_DIMENSIONS},
            'anchor_strength': 'adequate',
            'feedback': '',
        })
        self.assertEqual(resp.status_code, 200)
        record.refresh_from_db()
        self.assertIsNotNone(record.graded_at)
        self.assertEqual(record.feedback, '')

    def test_a_draft_request_that_fails_returns_a_reason_not_an_error(self):
        """The modal asks for a draft on open. A dead model must degrade to an
        empty box the instructor can type into, never a failed dialog."""
        record = self._record()
        request = APIRequestFactory().post(f'/api/instructor/score/{record.id}/feedback-draft/')
        force_authenticate(request, user=self.instructor)
        with patch('feedback.services.get_llm_client', side_effect=RuntimeError('model down')):
            resp = InstructorFeedbackDraftView.as_view()(request, score_id=record.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['feedback'], '')
        self.assertIn('could not be generated', resp.data['problem'])

    def test_regrading_without_feedback_leaves_published_feedback_alone(self):
        """Absent from the payload means 'leave it', so an instructor nudging a
        number does not silently unpublish what the firm already read."""
        record = self._record()
        self._post(record, {
            'scores': {d: 0 for d in SCORE_DIMENSIONS},
            'anchor_strength': 'adequate',
            'feedback': 'What held was the anchor.',
        })
        self._post(record, {
            'scores': {d: 1 for d in SCORE_DIMENSIONS}, 'anchor_strength': 'adequate',
        })
        record.refresh_from_db()
        self.assertEqual(record.feedback, 'What held was the anchor.')


class FeedbackPublishTimingTests(TestCase):
    """When does a student see written feedback? Answer: the moment the grade
    saves. There is no separate release step. This test exists to pin that
    behaviour down so a future hold-until-released switch is a deliberate
    change and not a silent one."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='pub-grader@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            username='pub-student@example.com', password='pw', role=UserRole.STUDENT,
        )
        cohort = Cohort.objects.create(name='SIM-PUB', tier=Tier.UNDERGRAD)
        cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(self.student)
        self.run = Run.objects.create(team=team)
        self.cohort = cohort

    def _performance(self):
        request = APIRequestFactory().get(f'/api/student/performance/?cohort={self.cohort.id}')
        force_authenticate(request, user=self.student)
        return StudentPerformanceView.as_view()(request)

    def test_feedback_is_visible_to_the_student_as_soon_as_the_grade_saves(self):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.student,
        )
        instance.refresh_from_db()
        record = instance.score_record

        # Before grading: the round is not even listed.
        self.assertEqual(self._performance().data['weeks'], [])

        request = APIRequestFactory().post(
            f'/api/instructor/score/{record.id}/',
            {
                'scores': {d: 0 for d in SCORE_DIMENSIONS},
                'anchor_strength': 'adequate',
                'feedback': 'What held was the anchor.',
            },
            format='json',
        )
        force_authenticate(request, user=self.instructor)
        InstructorScoreView.as_view()(request, score_id=record.id)

        # After grading: immediately readable. No release step stands between.
        weeks = self._performance().data['weeks']
        self.assertEqual(len(weeks), 1)
        self.assertEqual(weeks[0]['feedback'], 'What held was the anchor.')


class AdvisorRateDefaultTests(TestCase):
    """A cohort nobody prices by hand must still cost something.

    The war-room UI only shows cost when the rate is above zero, so a cohort
    defaulting to 0 would look like it was working while quietly making
    consultation free — and advisor scarcity is what forces triage.
    """

    def test_new_cohort_defaults_to_the_real_rate(self):
        cohort = Cohort.objects.create(name='SIM-DEFAULT', tier=Tier.UNDERGRAD)
        self.assertEqual(cohort.advisor_hourly_rate, DEFAULT_ADVISOR_HOURLY_RATE)
        self.assertEqual(cohort.advisor_hourly_rate, 300)

    def test_the_admin_endpoint_will_not_create_a_cohort_without_a_rate(self):
        """The create endpoint now requires the rate rather than defaulting it.

        That is deliberately stricter than the model default: a rate quietly
        applied on the server is a rate nobody chose, and the failure mode —
        free consultation that looks like it is working — is the one we care
        about. The admin form pre-fills 300, so the rate is always a visible,
        deliberate figure by the time it reaches here.
        """
        admin = User.objects.create_user(
            username='admin@example.com', password='pw', role=UserRole.INSTRUCTOR,
            is_staff=True, is_superuser=True,
        )

        def post(body):
            request = APIRequestFactory().post('/api/admin/simulations/', body, format='json')
            force_authenticate(request, user=admin)
            return AdminSimulationsView.as_view()(request)

        base = {
            'name': 'SIM-NEW', 'tier': Tier.UNDERGRAD, 'teams': 2, 'team_size': 4,
            'enrollment_capacity': 30, 'days_per_round': 7, 'price_per_student': 0,
            'timezone': 'UTC', 'start_date': '2026-09-01',
        }
        rejected = post(base)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('advisor_hourly_rate', rejected.data['errors'])

        created = post({**base, 'advisor_hourly_rate': DEFAULT_ADVISOR_HOURLY_RATE})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Cohort.objects.get(name='SIM-NEW').advisor_hourly_rate, 300)

    def test_a_four_advisor_room_hour_bills_four_times_the_rate(self):
        cohort = Cohort.objects.create(name='SIM-ROOM4', tier=Tier.UNDERGRAD)
        student = User.objects.create_user(username='room4@example.com', password='pw', role=UserRole.STUDENT)
        team = Team.objects.create(cohort=cohort, name='Team 1')
        team.members.add(student)
        Enrollment.objects.create(cohort=cohort, student=student, team=team)
        run = Run.objects.create(team=team, current_week=1)
        room = GroupSession.objects.create(
            run=run, week_number=1, active_advisors=['a', 'b', 'c', 'd'],
        )
        billed = GroupConversationView._meter_group_session(student, run, room)
        self.assertEqual(billed.billed, 1200)


class AdminCreateSimulationValidationTests(TestCase):
    """Creating a simulation used to accept almost anything: a blank tier became
    UNDERGRAD, a cleared team count became 0 firms, an unparseable date became
    None, and out-of-range numbers were silently clamped. Every one of those
    produced a simulation that quietly wasn't what the admin typed.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='root@example.com', password='pw', role=UserRole.INSTRUCTOR,
            is_staff=True, is_superuser=True,
        )

    def _post(self, body):
        request = APIRequestFactory().post('/api/admin/simulations/', body, format='json')
        force_authenticate(request, user=self.admin)
        return AdminSimulationsView.as_view()(request)

    def _valid(self, **overrides):
        body = {
            'name': 'SIM-VALID', 'tier': Tier.GRADUATE, 'teams': 3,
            'team_size': 4, 'enrollment_capacity': 30, 'days_per_round': 7,
            'price_per_student': 100, 'advisor_hourly_rate': 300,
            'timezone': 'UTC', 'start_date': '2026-09-01',
        }
        body.update(overrides)
        return body

    def test_a_complete_payload_creates_the_simulation(self):
        resp = self._post(self._valid())
        self.assertEqual(resp.status_code, 201)
        cohort = Cohort.objects.get(name='SIM-VALID')
        self.assertEqual(cohort.tier, Tier.GRADUATE)
        self.assertEqual(cohort.advisor_hourly_rate, 300)
        self.assertEqual(Team.objects.filter(cohort=cohort).count(), 3)

    def test_an_empty_payload_reports_every_missing_field(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)
        errors = resp.data['errors']
        for field in ('name', 'tier', 'teams', 'team_size', 'enrollment_capacity',
                      'days_per_round', 'price_per_student', 'advisor_hourly_rate',
                      'timezone', 'start_date'):
            self.assertIn(field, errors, f'{field} was accepted while missing')
        self.assertFalse(Cohort.objects.exists())

    def test_blank_and_malformed_values_are_rejected_not_defaulted(self):
        cases = [
            ({'name': '   '}, 'name'),
            ({'tier': 'POSTGRAD'}, 'tier'),
            ({'teams': ''}, 'teams'),
            ({'teams': 'four'}, 'teams'),
            ({'teams': 0}, 'teams'),
            ({'teams': 99}, 'teams'),
            ({'team_size': 0}, 'team_size'),
            ({'days_per_round': 0}, 'days_per_round'),
            ({'advisor_hourly_rate': -1}, 'advisor_hourly_rate'),
            ({'start_date': ''}, 'start_date'),
            ({'start_date': 'next tuesday'}, 'start_date'),
            ({'timezone': ''}, 'timezone'),
        ]
        for override, field in cases:
            resp = self._post(self._valid(**override))
            self.assertEqual(resp.status_code, 400, f'{override} was accepted')
            self.assertIn(field, resp.data['errors'], f'{override} did not flag {field}')
        self.assertFalse(Cohort.objects.exists())

    def test_capacity_must_hold_the_firms_it_is_given(self):
        resp = self._post(self._valid(teams=10, team_size=5, enrollment_capacity=20))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('enrollment_capacity', resp.data['errors'])

    def test_duplicate_names_are_rejected(self):
        self.assertEqual(self._post(self._valid()).status_code, 201)
        resp = self._post(self._valid(name='sim-valid'))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('name', resp.data['errors'])
        self.assertEqual(Cohort.objects.count(), 1)


class InstructorFirmManagementTests(TestCase):
    """Faculty create and delete firms, and allocate students into them.

    Deletion is the dangerous one: Run is a OneToOne on Team with CASCADE, so a
    firm carries its run, week instances, submissions and score records down
    with it. These tests pin the guards that stop that happening by accident.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='firms@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.cohort = Cohort.objects.create(name='SIM-FIRMS', tier=Tier.UNDERGRAD)
        self.cohort.instructors.add(self.instructor)
        self.other = User.objects.create_user(
            username='notmine@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )

    def _create(self, body=None, user=None):
        request = APIRequestFactory().post('/x', body or {}, format='json')
        force_authenticate(request, user=user or self.instructor)
        return InstructorFirmsView.as_view()(request, cohort_id=self.cohort.id)

    def _delete(self, firm_number, user=None):
        request = APIRequestFactory().delete('/x')
        force_authenticate(request, user=user or self.instructor)
        return InstructorFirmDetailView.as_view()(
            request, cohort_id=self.cohort.id, firm_number=firm_number,
        )

    def test_creating_a_firm_also_creates_its_run(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'Team 1')
        team = Team.objects.get(cohort=self.cohort, name='Team 1')
        self.assertTrue(Run.objects.filter(team=team).exists())

    def test_default_names_skip_over_names_already_taken(self):
        self._create()                      # Team 1
        self._create()                      # Team 2
        self._delete(1)                     # remove Team 1, leaving Team 2
        resp = self._create()
        # Counting would have proposed "Team 2", which already exists.
        self.assertEqual(resp.data['name'], 'Team 1')

    def test_a_named_firm_is_accepted_and_duplicates_are_not(self):
        self.assertEqual(self._create({'name': 'Northwind'}).status_code, 201)
        clash = self._create({'name': 'northwind'})
        self.assertEqual(clash.status_code, 400)
        self.assertEqual(Team.objects.filter(cohort=self.cohort).count(), 1)

    def test_an_empty_firm_can_be_deleted(self):
        self._create()
        resp = self._delete(1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Team.objects.filter(cohort=self.cohort).count(), 0)
        self.assertEqual(Run.objects.filter(team__cohort=self.cohort).count(), 0)

    def test_a_firm_with_students_in_it_cannot_be_deleted(self):
        self._create()
        team = Team.objects.get(cohort=self.cohort)
        student = User.objects.create_user(username='s@example.com', password='pw', role=UserRole.STUDENT)
        team.members.add(student)

        resp = self._delete(1)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('Move them out first', resp.data['detail'])
        self.assertTrue(Team.objects.filter(cohort=self.cohort).exists())

    def test_a_firm_with_submitted_work_cannot_be_deleted(self):
        self._create()
        team = Team.objects.get(cohort=self.cohort)
        run = Run.objects.get(team=team)
        WeekInstance.objects.create(run=run, week_number=1, status=WeekInstanceStatus.SUBMITTED)

        resp = self._delete(1)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('cannot be recovered', resp.data['detail'])
        self.assertTrue(Run.objects.filter(team=team).exists())

    def test_another_instructors_cohort_is_untouchable(self):
        self.assertEqual(self._create(user=self.other).status_code, 404)
        self._create()
        self.assertEqual(self._delete(1, user=self.other).status_code, 404)
        self.assertTrue(Team.objects.filter(cohort=self.cohort).exists())

    def test_allocating_and_unallocating_a_student(self):
        self._create()
        team = Team.objects.get(cohort=self.cohort)
        student = User.objects.create_user(username='alloc@example.com', password='pw', role=UserRole.STUDENT)
        enrollment = Enrollment.objects.create(cohort=self.cohort, student=student)

        def move(firm_number):
            request = APIRequestFactory().post('/x', {'firm_number': firm_number}, format='json')
            force_authenticate(request, user=self.instructor)
            return InstructorMoveEnrollmentView.as_view()(
                request, cohort_id=self.cohort.id, enrollment_id=enrollment.id,
            )

        self.assertEqual(move(1).status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.team, team)
        self.assertIn(student, team.members.all())

        self.assertEqual(move(0).status_code, 200)   # back to unallocated
        enrollment.refresh_from_db()
        self.assertIsNone(enrollment.team)
        self.assertNotIn(student, team.members.all())


class StartDateChangeTests(TestCase):
    """Faculty move a term's start date and the whole round calendar follows.

    The calendar is derived from start_date on every read rather than stored, so
    the schedule regenerates by itself — these pin that it actually does, and
    that extensions granted earlier survive the move.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='sched@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.cohort = Cohort.objects.create(
            name='SIM-SCHED', tier=Tier.UNDERGRAD,
            start_date=date(2026, 9, 1), days_per_week=7,
        )
        self.cohort.instructors.add(self.instructor)
        team = Team.objects.create(cohort=self.cohort, name='Team 1')
        Run.objects.create(team=team, current_week=1)

    def _patch(self, body, user=None):
        request = APIRequestFactory().patch('/x', body, format='json')
        force_authenticate(request, user=user or self.instructor)
        return InstructorSimulationDetailView.as_view()(request, cohort_id=self.cohort.id)

    def test_moving_the_start_date_rebuilds_every_round(self):
        before = self._patch({'start_date': '2026-09-01'}).data['rounds']
        resp = self._patch({'start_date': '2026-09-08'})   # a week later

        self.assertEqual(resp.status_code, 200)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.start_date, date(2026, 9, 8))
        self.assertEqual(resp.data['previous_start_date'], '2026-09-01')

        after = resp.data['rounds']
        self.assertEqual(len(after), len(before))
        # Every round moved, not just the first.
        self.assertNotEqual(after[0]['start'], before[0]['start'])
        self.assertNotEqual(after[-1]['end'], before[-1]['end'])
        self.assertIn('Sep 8, 2026', after[0]['start'])

    def test_extensions_survive_the_move(self):
        self.cohort.round_extensions = {'2': 3}
        self.cohort.save(update_fields=['round_extensions'])

        rounds = self._patch({'start_date': '2026-10-01'}).data['rounds']
        self.assertEqual(rounds[1]['extended_days'], 3)
        # R2 is three days longer than the 7-day default, so R3 starts later.
        self.assertEqual(rounds[1]['end'], rounds[2]['start'])

    def test_a_bad_date_is_rejected_and_nothing_moves(self):
        for bad in ('', 'next tuesday', '2026-13-45'):
            resp = self._patch({'start_date': bad})
            self.assertEqual(resp.status_code, 400, bad)
            self.assertIn('start_date', resp.data['errors'])
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.start_date, date(2026, 9, 1))

    def test_the_rate_and_the_date_can_move_together(self):
        resp = self._patch({'start_date': '2026-11-02', 'advisor_hourly_rate': 250})
        self.assertEqual(resp.status_code, 200)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.start_date, date(2026, 11, 2))
        self.assertEqual(self.cohort.advisor_hourly_rate, 250)

    def test_an_empty_patch_is_refused(self):
        self.assertEqual(self._patch({}).status_code, 400)


class ImpossibleDateOnCreateTests(TestCase):
    """A well-formed but impossible date used to raise out of parse_date and
    500 the create endpoint instead of being reported as a field error."""

    def test_an_impossible_date_is_a_field_error_not_a_crash(self):
        admin = User.objects.create_user(
            username='dates@example.com', password='pw', role=UserRole.INSTRUCTOR,
            is_staff=True, is_superuser=True,
        )
        request = APIRequestFactory().post('/api/admin/simulations/', {
            'name': 'SIM-BADDATE', 'tier': Tier.UNDERGRAD, 'teams': 2, 'team_size': 4,
            'enrollment_capacity': 30, 'days_per_round': 7, 'price_per_student': 0,
            'advisor_hourly_rate': 300, 'timezone': 'UTC', 'start_date': '2026-13-45',
        }, format='json')
        force_authenticate(request, user=admin)
        resp = AdminSimulationsView.as_view()(request)

        self.assertEqual(resp.status_code, 400)
        self.assertIn('start_date', resp.data['errors'])
        self.assertFalse(Cohort.objects.filter(name='SIM-BADDATE').exists())


class AdminCreateFacultyTests(TestCase):
    """The admin console could list faculty but never create one, so a cohort
    could only be handed to someone who already had an account."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='super@example.com', password='pw', role=UserRole.INSTRUCTOR,
            is_staff=True, is_superuser=True,
        )

    def _post(self, body, user=None):
        request = APIRequestFactory().post('/api/admin/faculty/', body, format='json')
        force_authenticate(request, user=user or self.admin)
        return AdminFacultyView.as_view()(request)

    def test_creating_faculty_emails_a_set_password_link(self):
        """No password is ever generated here. The instructor chooses their own
        from an emailed link, so nobody else ever knows it — an admin reading a
        generated password aloud is a credential in the clear."""
        resp = self._post({'email': 'New.Prof@Example.com', 'first_name': 'Ada', 'last_name': 'Byron'})
        self.assertEqual(resp.status_code, 201)

        user = User.objects.get(username='new.prof@example.com')
        self.assertEqual(user.role, UserRole.INSTRUCTOR)
        self.assertEqual(user.first_name, 'Ada')
        self.assertEqual(resp.data['name'], 'Ada Byron')

        self.assertNotIn('temp_password', resp.data)
        self.assertFalse(user.has_usable_password())

    def test_the_new_instructor_can_be_assigned_to_a_cohort(self):
        created = self._post({'email': 'teach@example.com', 'first_name': 'Grace'})
        cohort = Cohort.objects.create(name='SIM-NEWFAC', tier=Tier.UNDERGRAD)
        cohort.instructors.add(User.objects.get(id=created.data['id']))
        self.assertEqual([i.username for i in cohort.instructors.all()], ['teach@example.com'])

    def test_duplicates_and_bad_input_are_reported_per_field(self):
        self._post({'email': 'dup@example.com', 'first_name': 'A'})
        cases = [
            ({'email': 'dup@example.com', 'first_name': 'A'}, 'email'),
            ({'email': 'DUP@example.com', 'first_name': 'A'}, 'email'),
            ({'email': 'not-an-email', 'first_name': 'A'}, 'email'),
            ({'email': '', 'first_name': 'A'}, 'email'),
            ({'email': 'ok@example.com', 'first_name': ''}, 'first_name'),
        ]
        for body, field in cases:
            resp = self._post(body)
            self.assertEqual(resp.status_code, 400, body)
            self.assertIn(field, resp.data['errors'], body)
        self.assertEqual(User.objects.filter(role=UserRole.INSTRUCTOR).count(), 2)  # admin + dup

    def test_an_email_belonging_to_a_student_is_refused(self):
        User.objects.create_user(username='stud@example.com', password='pw', role=UserRole.STUDENT)
        resp = self._post({'email': 'stud@example.com', 'first_name': 'A'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already belongs', resp.data['errors']['email'])

    def test_a_plain_instructor_cannot_create_faculty(self):
        plain = User.objects.create_user(
            username='plain@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.assertEqual(self._post({'email': 'x@example.com', 'first_name': 'A'}, user=plain).status_code, 403)


class CoFacultyTests(TestCase):
    """Faculty staff their own cohort. Previously only an admin could attach an
    instructor, at provisioning, so bringing in a TA mid-term meant going back
    to whoever holds admin."""

    def setUp(self):
        from mailer import backends
        from mailer.backends import LocmemBackend
        self.outbox = LocmemBackend()
        backends.set_backend(self.outbox)
        self.addCleanup(backends.set_backend, None)

        self.owner = User.objects.create_user(
            username='owner@example.com', password='pw', role=UserRole.INSTRUCTOR, first_name='Ada',
        )
        self.cohort = Cohort.objects.create(name='SIM-COFAC', tier=Tier.UNDERGRAD)
        self.cohort.instructors.add(self.owner)
        self.outsider = User.objects.create_user(
            username='outsider@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )

    def _add(self, body, user=None):
        request = APIRequestFactory().post('/x', body, format='json')
        force_authenticate(request, user=user or self.owner)
        return InstructorCoFacultyView.as_view()(request, cohort_id=self.cohort.id)

    def _remove(self, user_id, user=None):
        request = APIRequestFactory().delete('/x')
        force_authenticate(request, user=user or self.owner)
        return InstructorCoFacultyDetailView.as_view()(
            request, cohort_id=self.cohort.id, user_id=user_id,
        )

    def test_adding_an_existing_instructor_attaches_them_without_email(self):
        resp = self._add({'email': 'outsider@example.com'})
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data['created'])
        self.assertIn(self.outsider, self.cohort.instructors.all())
        self.assertEqual(len(self.outbox.outbox), 0)   # they already have an account

    def test_adding_an_unknown_address_creates_them_and_sends_a_set_password_link(self):
        resp = self._add({'email': 'ta@example.com', 'first_name': 'Grace', 'last_name': 'Hopper'})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['created'])
        self.assertTrue(resp.data['invite_sent'])

        ta = User.objects.get(username='ta@example.com')
        self.assertEqual(ta.role, UserRole.INSTRUCTOR)
        self.assertFalse(ta.has_usable_password())
        self.assertIn(ta, self.cohort.instructors.all())
        self.assertIn('/set-password/', self.outbox.outbox[0].text)

    def test_a_new_instructor_needs_a_name(self):
        resp = self._add({'email': 'nameless@example.com'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('first_name', resp.data['errors'])
        self.assertFalse(User.objects.filter(username='nameless@example.com').exists())

    def test_duplicates_students_and_junk_are_refused(self):
        self._add({'email': 'outsider@example.com'})
        User.objects.create_user(username='pupil@example.com', password='pw', role=UserRole.STUDENT)
        for body, field in [
            ({'email': 'outsider@example.com'}, 'email'),   # already teaches it
            ({'email': 'pupil@example.com'}, 'email'),      # a student account
            ({'email': 'nope'}, 'email'),
        ]:
            resp = self._add(body)
            self.assertEqual(resp.status_code, 400, body)
            self.assertIn(field, resp.data['errors'], body)

    def test_removing_a_co_teacher_leaves_the_account_alone(self):
        self._add({'email': 'outsider@example.com'})
        resp = self._remove(self.outsider.id)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.outsider, self.cohort.instructors.all())
        self.assertTrue(User.objects.filter(pk=self.outsider.pk).exists())

    def test_the_last_instructor_cannot_be_removed(self):
        """A cohort with nobody teaching it is unreachable — every instructor
        endpoint scopes by who teaches it, so no one could add one back."""
        resp = self._remove(self.owner.id)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('only instructor', resp.data['detail'])
        self.assertIn(self.owner, self.cohort.instructors.all())

    def test_someone_elses_cohort_is_untouchable(self):
        self.assertEqual(self._add({'email': 'x@example.com', 'first_name': 'X'},
                                   user=self.outsider).status_code, 404)
        self.assertEqual(self._remove(self.owner.id, user=self.outsider).status_code, 404)


class MailConfigVisibilityTests(TestCase):
    """The console backend 'succeeds' by printing, so invitations stamp as sent
    while nothing leaves the server. Faculty have to be told that at the server
    level, or the delivery counter reads green and lies."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='mailcfg@example.com', password='pw', role=UserRole.INSTRUCTOR,
        )
        self.cohort = Cohort.objects.create(name='SIM-MAILCFG', tier=Tier.UNDERGRAD)
        self.cohort.instructors.add(self.instructor)

    def _detail(self):
        request = APIRequestFactory().get('/x')
        force_authenticate(request, user=self.instructor)
        return InstructorSimulationDetailView.as_view()(request, cohort_id=self.cohort.id)

    def test_console_backend_reports_mail_as_not_configured(self):
        with self.settings(MAIL_BACKEND='console'):
            mail = self._detail().data['mail']
        self.assertEqual(mail['backend'], 'console')
        self.assertFalse(mail['configured'])

    def test_mailjet_without_credentials_is_still_not_configured(self):
        with self.settings(MAIL_BACKEND='mailjet', MAILJET_API_KEY='', MAILJET_API_SECRET='',
                           MAIL_FROM_ADDRESS=''):
            self.assertFalse(self._detail().data['mail']['configured'])

    def test_fully_configured_mailjet_reports_live(self):
        with self.settings(MAIL_BACKEND='mailjet', MAILJET_API_KEY='k',
                           MAILJET_API_SECRET='s', MAIL_FROM_ADDRESS='from@example.com'):
            mail = self._detail().data['mail']
        self.assertTrue(mail['configured'])
        self.assertEqual(mail['backend'], 'mailjet')

    def test_the_console_backend_still_stamps_an_invitation_as_sent(self):
        """Documents the trap this warning exists for: sent_at is set even
        though nothing was emailed, so per-row status alone cannot reveal it."""
        import secrets as _s
        from mailer import backends
        from mailer.invites import send_invitation
        backends.set_backend(backends.ConsoleBackend())
        self.addCleanup(backends.set_backend, None)

        inv = Invitation.objects.create(
            cohort=self.cohort, email='x@example.com', token=_s.token_urlsafe(24),
        )
        sent, _detail = send_invitation(inv)
        inv.refresh_from_db()
        self.assertTrue(sent)
        self.assertIsNotNone(inv.sent_at)
        self.assertEqual(inv.send_error, '')


class StudentBenchmarkStateTests(TestCase):
    """What a student may learn about withheld standings.

    Enough to know it is pending rather than broken, and nothing more: no firm
    names, no count of who is outstanding, no partial figures. A count is a
    small leak that compounds across a cohort that talks to each other.
    """

    def setUp(self):
        self.cohort = Cohort.objects.create(name='SIM-BSTATE', tier=Tier.UNDERGRAD)
        self.firms = []
        for n in (1, 2):
            team = Team.objects.create(cohort=self.cohort, name=f'Team {n}')
            student = User.objects.create_user(
                username=f'bstate-{n}@example.com', password='pw', role=UserRole.STUDENT,
            )
            team.members.add(student)
            Enrollment.objects.create(cohort=self.cohort, student=student, team=team)
            self.firms.append((Run.objects.create(team=team), student))

    def _performance(self, student):
        request = APIRequestFactory().get(f'/api/student/performance/?cohort={self.cohort.id}')
        force_authenticate(request, user=student)
        return StudentPerformanceView.as_view()(request).data

    def _play_to_week_4(self, run, student):
        from weeks.tests import week2_payload, week3_payload, week4_payload
        payloads = {1: week1_payload, 2: week2_payload, 3: week3_payload, 4: week4_payload}
        for week in range(1, 5):
            run.refresh_from_db()
            run.current_week = week
            run.save()
            instance = view_briefing(run)
            submit_week(
                instance,
                structured_payload=payloads[week](),
                deliverable_text='A considered memo with a clear plan.',
                submitted_by=student,
            )
            instance.refresh_from_db()
            if week < 4:
                finalize_score(instance.score_record)
        return instance.score_record

    def test_before_any_checkpoint_there_is_nothing_to_say(self):
        run, student = self.firms[0]
        self.assertIsNone(self._performance(student)['benchmark'])

    def test_pending_is_stated_without_naming_anyone(self):
        records = [self._play_to_week_4(run, s) for run, s in self.firms]
        finalize_score(records[0])  # one firm graded, one outstanding

        run, student = self.firms[0]
        run.refresh_from_db()
        state = self._performance(student)['benchmark']
        self.assertEqual(state, {'after_week': 4, 'status': 'pending'})

        # Nothing about who, how many, or how they are doing.
        blob = str(self._performance(student)).lower()
        for leak in ('team 2', 'team 1', 'pending_firms', 'standings', 'rank'):
            self.assertNotIn(leak, blob, f'student payload leaked {leak!r}')

    def test_it_flips_to_published_when_the_last_firm_is_graded(self):
        records = [self._play_to_week_4(run, s) for run, s in self.firms]
        for record in records:
            finalize_score(record)

        run, student = self.firms[0]
        run.refresh_from_db()
        self.assertEqual(
            self._performance(student)['benchmark'],
            {'after_week': 4, 'status': 'published'},
        )
