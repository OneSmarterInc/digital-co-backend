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
    InstructorFirmDetailView, InstructorFirmsView, InstructorMoveEnrollmentView,
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
