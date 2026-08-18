"""Multi-simulation run resolution.

A student can be enrolled in several simulations at once — one Team + Run per
cohort. These tests pin the behavior that keeps those enrollments independent:
run resolution must be scoped to the cohort the request targets, not collapse
onto an arbitrary Run.first(). Regression guard for the bug where every student
runtime endpoint served whichever run happened to come back first.
"""
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from django.db.models import Count, Sum

from advisors.models import (
    BILLED, AdvisorDefinition, AdvisorSession, Conversation, GroupSession,
)
from core.models import (
    DEFAULT_ADVISOR_HOURLY_RATE, Cohort, Enrollment, Run, Team, Tier, User, UserRole,
)
from core.state import SCORE_DIMENSIONS
from engine.services import submit_week, view_briefing
from weeks.tests import week1_payload
from scoring.models import ScoreRecord
from weeks.models import Submission, WeekInstance, WeekInstanceStatus

from .instructor_api import (
    InstructorSimulationDetailView, _advisor_usage_by_student, _billing,
)
from .views import (
    AdminSimulationsView, GroupConversationView, InstructorQueueView,
    InstructorScoreView, RunView, resolve_run, run_for_user,
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

    def test_cohort_created_through_the_admin_endpoint_gets_the_rate(self):
        admin = User.objects.create_user(
            username='admin@example.com', password='pw', role=UserRole.INSTRUCTOR,
            is_staff=True, is_superuser=True,
        )
        request = APIRequestFactory().post(
            '/api/admin/simulations/', {'name': 'SIM-NEW', 'tier': Tier.UNDERGRAD}, format='json',
        )
        force_authenticate(request, user=admin)
        resp = AdminSimulationsView.as_view()(request)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            Cohort.objects.get(name='SIM-NEW').advisor_hourly_rate, DEFAULT_ADVISOR_HOURLY_RATE,
        )

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
