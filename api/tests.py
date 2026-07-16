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

from core.models import Cohort, Run, Team, Tier, User, UserRole
from scoring.models import ScoreRecord
from weeks.models import Submission, WeekInstance, WeekInstanceStatus

from .views import InstructorQueueView, RunView, resolve_run, run_for_user


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
