"""JSON API over the existing DigitalCo services.

Every endpoint wraps a service function the Django template views already use
(view_briefing, submit_week, finalize_score, generate_debrief, the benchmark
builders), so the API and the current web UI share one source of truth. Auth is
JWT: clients obtain a token at /api/token/ and send it as a Bearer header.
"""
import json as _json
import os as _os
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings as django_settings
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from advisors.models import AdvisorDefinition, AdvisorSession, Conversation, Message, MessageRole
from advisors.services import AdvisorService
from core.models import Cohort, Enrollment, Run, RunStatus, Team, Tier, User, UserRole
from core.state import SCORE_DIMENSIONS
from engine.climax import generate_debrief
from engine.services import (
    InvalidTransition, get_or_create_week_instance, submit_week, view_briefing,
)
from scoring.models import Benchmark, ScoreRecord
from scoring.services import finalize_score, student_benchmark_payload
from weeks.models import WeekInstanceStatus
from weeks.registry import registry

from . import serialize
from .permissions import IsAdmin, IsInstructor
from django.db.models import Max
from django.utils.dateparse import parse_date
from django.utils import timezone as dj_timezone
from datetime import timedelta
ANCHOR_STRENGTHS = ('strong', 'adequate', 'weak')


def run_for_user(user):
    return Run.objects.select_related('team__cohort').filter(team__members=user).first()


def briefing_for(module, tier, run):
    if hasattr(module, 'briefing_for_run'):
        return module.briefing_for_run(tier, run)
    return module.briefing(tier)


def blocked_response(user, run):
    """403 when the requesting student's enrollment in this run's cohort is
    blocked. Blocking must hold at the API, not just in the portal UI —
    otherwise a kept-open tab or a direct API call plays on (and advisor
    chat spends real LLM/TTS money) while the student is 'blocked'. This
    also makes Block a true kill switch even though already-issued JWTs
    remain valid until expiry."""
    from core.models import Enrollment
    enrollment = Enrollment.objects.filter(student=user, cohort=run.team.cohort).first()
    if enrollment and enrollment.blocked:
        return Response(
            {'detail': 'Your access to this cohort has been paused by your instructor.'},
            status=403,
        )
    return None


def no_run_response():
    return Response({'detail': 'No run is assigned to this user.'}, status=404)


class MeView(APIView):
    """Who am I, and which run/cohorts do I belong to. Drives frontend routing."""

    def get(self, request):
        user = request.user
        run = run_for_user(user)
        is_instructor = user.role == UserRole.INSTRUCTOR
        return Response({
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'is_instructor': is_instructor,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'run_id': run.id if run else None,
            'current_week': run.current_week if run else None,
            'team': run.team.name if run else None,
            'cohort': run.team.cohort.name if run else None,
            'instructed_cohorts': (
                [{'id': c.id, 'name': c.name} for c in user.instructed_cohorts.all()]
                if is_instructor else []
            ),
        })


class RunView(APIView):
    """The whole weekly student screen in one payload."""

    def get(self, request):
        run = run_for_user(request.user)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        instance = view_briefing(run)
        module = registry.get(instance.week_number)
        tier = run.team.cohort.tier
        week14 = run.week_instances.filter(week_number=14).first()
        debrief_ready = bool(
            run.status == RunStatus.COMPLETE
            or (week14 and week14.status in (WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED))
        )
        return Response({
            'run': {
                'id': run.id,
                'current_week': run.current_week,
                'status': run.status,
                'tier_outcome': run.tier_outcome,
            },
            'week': serialize.week_status(instance),
            'briefing': serialize.briefing_json(briefing_for(module, tier, run)),
            'artifacts': serialize.artifacts_json(module.artifacts(tier)),
            'decision_spec': serialize.decision_spec_json(module.decision_spec(tier)),
            'advisors': [serialize.advisor_json(a) for a in AdvisorDefinition.objects.filter(active=True)],
            'debrief_available': debrief_ready,
        })


class SubmitView(APIView):
    """Submit the current week's decision, with a clean guard on resubmits."""

    def post(self, request):
        run = run_for_user(request.user)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        instance = get_or_create_week_instance(run)
        if instance.status not in (WeekInstanceStatus.BRIEFING, WeekInstanceStatus.CONSULTATION):
            return Response(
                {'detail': 'This week has already been submitted.', 'week': serialize.week_status(instance)},
                status=409,
            )
        module = registry.get(instance.week_number)
        raw = request.data.get('payload') or {}
        payload = {}
        for field in module.decision_spec(run.team.cohort.tier).fields:
            if field.field_type == 'boolean':
                payload[field.key] = bool(raw.get(field.key, False))
            else:
                payload[field.key] = raw.get(field.key)
        try:
            submit_week(
                instance,
                structured_payload=payload,
                deliverable_text=request.data.get('deliverable_text', ''),
                submitted_by=request.user,
            )
        except InvalidTransition as exc:
            return Response({'detail': str(exc)}, status=409)
        instance.refresh_from_db()
        return Response({'week': serialize.week_status(instance)})


class AdvanceView(APIView):
    """Move the run to the next week once this one is in. The missing 'next' step."""

    def post(self, request):
        run = run_for_user(request.user)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        instance = get_or_create_week_instance(run)
        if instance.status not in (WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED):
            return Response({'detail': 'Submit this week before advancing.'}, status=409)
        if run.current_week >= 14:
            run.status = RunStatus.COMPLETE
            run.save()
            return Response({'run': {'current_week': run.current_week, 'status': run.status}, 'detail': 'Run complete.'})
        run.current_week += 1
        run.save()
        return Response({'run': {'current_week': run.current_week, 'status': run.status}})


class DebriefView(APIView):
    """The Week 14 payoff screen, powered by the engine's own debrief."""

    def get(self, request):
        run = run_for_user(request.user)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        week14 = run.week_instances.filter(week_number=14).first()
        ready = bool(
            run.status == RunStatus.COMPLETE
            or (week14 and week14.status in (WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED))
        )
        if not ready:
            return Response({'detail': 'The debrief is available once Week 14 is submitted.'}, status=409)
        return Response(generate_debrief(run.state))


class AdvisorListView(APIView):
    def get(self, request):
        return Response([serialize.advisor_json(a) for a in AdvisorDefinition.objects.filter(active=True)])


class AdvisorConversationView(APIView):
    """Read or post to a single advisor's conversation for the current week."""

    def _resolve(self, request, advisor_id):
        run = run_for_user(request.user)
        if not run:
            return None
        # Enforce blocking before anything is created: a blocked student must
        # not open conversations or trigger LLM calls.
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        advisor = get_object_or_404(AdvisorDefinition, id=advisor_id, active=True)
        instance = get_or_create_week_instance(run)
        conversation, _ = Conversation.objects.get_or_create(
            run=run, week_number=instance.week_number, advisor=advisor,
        )
        return run, advisor, instance, conversation

    def get(self, request, advisor_id):
        resolved = self._resolve(request, advisor_id)
        if resolved is None:
            return no_run_response()
        if isinstance(resolved, Response):
            return resolved
        _, _, _, conversation = resolved
        return Response(serialize.conversation_json(conversation))

    def post(self, request, advisor_id):
        resolved = self._resolve(request, advisor_id)
        if resolved is None:
            return no_run_response()
        if isinstance(resolved, Response):
            return resolved
        run, advisor, instance, conversation = resolved
        content = (request.data.get('content') or '').strip()
        if content:
            self._meter_session(request.user, run, conversation)
            Message.objects.create(conversation=conversation, role=MessageRole.STUDENT, content=content)
            module = registry.get(instance.week_number)
            AdvisorService().respond(
                advisor=advisor,
                conversation=conversation,
                run_state=run.state,
                week_context=module.advisor_context(advisor.key, run.team.cohort.tier, run.state),
                tier=run.team.cohort.tier,
            )
        conversation.refresh_from_db()
        return Response(serialize.conversation_json(conversation))

    @staticmethod
    def _meter_session(user, run, conversation):
        """Hourly advisor billing. The first message opens a one-hour session at the
        cohort's advisor rate; messages inside that hour are covered, and the next
        message after it opens (and bills) a new session. Rate 0 still records the
        hour so usage stays visible, it just bills nothing."""
        cohort = run.team.cohort
        now = dj_timezone.now()
        open_session = (
            AdvisorSession.objects
            .filter(conversation=conversation, student=user, started_at__gt=now - timedelta(hours=1))
            .order_by('-started_at')
            .first()
        )
        if open_session:
            open_session.last_activity_at = now
            open_session.save(update_fields=['last_activity_at'])
            return open_session
        enrollment = Enrollment.objects.filter(cohort=cohort, student=user).first()
        return AdvisorSession.objects.create(
            conversation=conversation,
            student=user,
            enrollment=enrollment,
            hourly_rate=cohort.advisor_hourly_rate or 0,
        )


class AdvisorSpeakView(APIView):
    """Speak one advisor message aloud via ElevenLabs, in that advisor's voice.

    POST {"message_id": n} -> audio/mpeg. The message must be an ADVISOR reply
    inside a conversation belonging to the requesting student's run — clients
    can't synthesize arbitrary text, only real replies, which keeps TTS spend
    bounded to actual gameplay. Voice ids come from advisor_agents.voices; the
    API key stays server-side (ELEVENLABS_API_KEY).
    """

    permission_classes = [IsAuthenticated]

    MAX_CHARS = 1200  # cost guard: clip very long replies

    def post(self, request, advisor_id):
        from advisor_agents.voices import get_voice_id

        run = run_for_user(request.user)
        if run is None:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        advisor = get_object_or_404(AdvisorDefinition, id=advisor_id)
        try:
            message_id = int(request.data.get('message_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'message_id is required.'}, status=400)
        message = get_object_or_404(
            Message,
            id=message_id,
            role=MessageRole.ADVISOR,
            conversation__run=run,
            conversation__advisor=advisor,
        )

        api_key = _os.environ.get('ELEVENLABS_API_KEY', '').strip()
        if not api_key:
            return Response({'detail': 'Voice is not configured on this server.'}, status=503)
        voice_id = get_voice_id(advisor.key)
        if not voice_id:
            return Response({'detail': 'No voice assigned to this advisor.'}, status=404)

        req = urllib.request.Request(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_64',
            data=_json.dumps({
                'text': message.content[: self.MAX_CHARS],
                'model_id': 'eleven_turbo_v2_5',
            }).encode('utf-8'),
            headers={'xi-api-key': api_key, 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as upstream:
                audio = upstream.read()
        except urllib.error.HTTPError as exc:
            return Response({'detail': f'Voice service error ({exc.code}).'}, status=502)
        except Exception:
            return Response({'detail': 'Voice service unreachable.'}, status=502)

        response = HttpResponse(audio, content_type='audio/mpeg')
        response['Cache-Control'] = 'no-store'
        return response


class AdvisorImageView(APIView):
    """Serve an advisor's portrait PNG from advisor_agents/images.

    Public by design: <img> tags can't attach JWT headers, and headshots are
    the least sensitive asset in the system. Filenames derive from the
    advisor's name ("Daniel Stern" -> Daniel_Stern_eyes_open.png); pass
    ?variant=closed for the blink frame. 404s cleanly when no file exists
    (e.g. inactive legacy advisors), so clients can fall back to initials.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, advisor_id):
        advisor = get_object_or_404(AdvisorDefinition, id=advisor_id)
        variant = 'closed' if request.query_params.get('variant') == 'closed' else 'open'
        filename = f"{advisor.name.replace(' ', '_')}_eyes_{variant}.png"
        path = Path(django_settings.BASE_DIR) / 'advisor_agents' / 'images' / filename
        if not path.is_file():
            return Response({'detail': 'No image for this advisor.'}, status=404)
        response = FileResponse(open(path, 'rb'), content_type='image/png')
        response['Cache-Control'] = 'public, max-age=86400'
        return response


class InstructorQueueView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        cohorts = request.user.instructed_cohorts.all()
        scores = (
            ScoreRecord.objects
            .select_related('week_instance__run__team__cohort')
            .filter(week_instance__run__team__cohort__in=cohorts)
            .order_by('week_instance__run__team__name', 'week_instance__week_number')
        )
        ungraded_only = request.query_params.get('ungraded') == '1'
        rows = [serialize.score_record_json(s) for s in scores]
        if ungraded_only:
            rows = [r for r in rows if not r['graded']]
        return Response(rows)


class InstructorScoreView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, score_id):
        score = get_object_or_404(ScoreRecord, id=score_id)
        scores = request.data.get('scores') or {}
        instructor_scores = {dimension: int(scores.get(dimension, 0)) for dimension in SCORE_DIMENSIONS}
        finalize_score(
            score,
            instructor_scores=instructor_scores,
            instructor_components=request.data.get('instructor_components') or {},
            graded_by=request.user,
        )
        anchor = request.data.get('anchor_strength')
        if anchor in ANCHOR_STRENGTHS and score.week_instance.week_number == 1:
            run = score.week_instance.run
            run.refresh_from_db()
            run.state['through_lines']['coherence']['anchor_strength'] = anchor
            run.save()
        score.refresh_from_db()
        return Response(serialize.score_record_json(score))


class InstructorBenchmarksView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        benchmarks = Benchmark.objects.filter(cohort=cohort).order_by('after_week')
        return Response([student_benchmark_payload(b) for b in benchmarks])

ADMIN_TOTAL_ROUNDS = 14


def _simulation_row(cohort):
    runs = Run.objects.filter(team__cohort=cohort)
    team_count = Team.objects.filter(cohort=cohort).count()
    current = runs.aggregate(m=Max('current_week'))['m'] or 0
    is_active = runs.filter(status=RunStatus.IN_PROGRESS).exists()
    return {
        'id': cohort.id,
        'name': cohort.name,
        'tier': cohort.tier,
        'status': 'active' if is_active else 'complete',
        'round': current,
        'total_rounds': ADMIN_TOTAL_ROUNDS,
        'teams': team_count,
        'progress': round(current / ADMIN_TOTAL_ROUNDS * 100) if current else 0,
    }


class AdminSimulationsView(APIView):
    """List every cohort as a 'simulation' (GET) or create one (POST)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        cohorts = list(Cohort.objects.all().order_by('id'))
        simulations = [_simulation_row(c) for c in cohorts]
        stats = {
            'total_games': len(simulations),
            'active': sum(1 for s in simulations if s['status'] == 'active'),
            'total_teams': sum(s['teams'] for s in simulations),
            'total_rounds': ADMIN_TOTAL_ROUNDS * len(simulations),
        }
        return Response({'stats': stats, 'simulations': simulations})

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'detail': 'A simulation name is required.'}, status=400)
        tier = request.data.get('tier')
        if tier not in (Tier.UNDERGRAD, Tier.GRADUATE):
            tier = Tier.UNDERGRAD
        try:
            team_count = int(request.data.get('teams') or 0)
        except (TypeError, ValueError):
            team_count = 0
        timezone = (request.data.get('timezone') or 'UTC').strip() or 'UTC'
        start_date = parse_date(request.data.get('start_date') or '')

        def clamped_int(key, default, lo, hi, alias=None):
            raw = request.data.get(key, request.data.get(alias) if alias else None)
            if raw in (None, ''):
                return default
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return default
            return max(lo, min(value, hi))

        # Provisioning the instructor console reads everywhere; the frontend says
        # "rounds" so days_per_round is accepted as an alias for days_per_week.
        days_per_week = clamped_int('days_per_week', 7, 1, 60, alias='days_per_round')
        team_size = clamped_int('team_size', 4, 1, 12)
        enrollment_capacity = clamped_int('enrollment_capacity', 30, 1, 1000)
        price_per_student = clamped_int('price_per_student', 0, 0, 100000)
        advisor_hourly_rate = clamped_int('advisor_hourly_rate', 0, 0, 100000)

        cohort = Cohort.objects.create(
            name=name,
            tier=tier,
            timezone=timezone,
            start_date=start_date,
            days_per_week=days_per_week,
            team_size=team_size,
            enrollment_capacity=enrollment_capacity,
            price_per_student=price_per_student,
            advisor_hourly_rate=advisor_hourly_rate,
        )

        # Cohort.instructors is many-to-many, so 'faculty' accepts a list of
        # instructor ids for co-taught courses. A single id (the old payload
        # shape) still works, and non-numeric entries are ignored.
        raw_faculty = request.data.get('faculty')
        if raw_faculty in (None, '', []):
            raw_faculty = []
        elif not isinstance(raw_faculty, (list, tuple)):
            raw_faculty = [raw_faculty]
        faculty_ids = []
        for value in raw_faculty:
            try:
                faculty_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        if faculty_ids:
            instructors = list(User.objects.filter(id__in=faculty_ids, role=UserRole.INSTRUCTOR))
            if instructors:
                cohort.instructors.add(*instructors)

        for index in range(max(0, min(team_count, 20))):
            team = Team.objects.create(cohort=cohort, name=f'Team {index + 1}')
            Run.objects.create(team=team)
        return Response(_simulation_row(cohort), status=201)


class AdminSimulationDetailView(APIView):
    """Delete a simulation (its cohort, teams, and runs cascade)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        cohort.delete()
        return Response(status=204)


class AdminSimulationTeamsView(APIView):
    """Add one team (with its run) to a simulation."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        count = Team.objects.filter(cohort=cohort).count()
        team = Team.objects.create(cohort=cohort, name=f'Team {count + 1}')
        Run.objects.create(team=team)
        return Response(_simulation_row(cohort), status=201)
    
class AdminPeopleView(APIView):
    """Admins, faculty, and students for the workspace views."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        admins, faculty, students, instructors = [], [], [], []
        for user in User.objects.all().order_by('username'):
            base = {'id': user.id, 'username': user.username, 'email': user.email or ''}
            is_admin_account = user.is_staff or user.is_superuser
            cohorts = (
                list(user.instructed_cohorts.values_list('name', flat=True))
                if user.role == UserRole.INSTRUCTOR else []
            )
            if user.role == UserRole.INSTRUCTOR:
                instructors.append({'id': user.id, 'username': user.username})
            # Each person lands in exactly one list. A teaching instructor is
            # faculty even if they're also a superuser; a staff/superuser who
            # teaches nothing is a pure admin; everyone else is a student.
            if user.role == UserRole.INSTRUCTOR and (cohorts or not is_admin_account):
                faculty.append({**base, 'cohorts': cohorts})
            elif is_admin_account:
                admins.append({**base, 'is_superuser': user.is_superuser})
            elif user.role == UserRole.STUDENT:
                team = Team.objects.filter(members=user).select_related('cohort').first()
                students.append({
                    **base,
                    'team': team.name if team else None,
                    'cohort': team.cohort.name if team else None,
                })
        return Response({'admins': admins, 'faculty': faculty, 'students': students, 'instructors': instructors})
    

class AdminSimulationDetailView(APIView):
    """Full detail for one simulation (GET) or delete it (DELETE)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        runs = Run.objects.filter(team__cohort=cohort)
        current = runs.aggregate(m=Max('current_week'))['m'] or 0
        is_active = runs.filter(status=RunStatus.IN_PROGRESS).exists()
        total = ADMIN_TOTAL_ROUNDS

        teams, students = [], []
        for team in Team.objects.filter(cohort=cohort).prefetch_related('members').order_by('name'):
            members = list(team.members.all())
            teams.append({'id': team.id, 'name': team.name, 'size': len(members)})
            for member in members:
                students.append({
                    'id': member.id,
                    'username': member.username,
                    'email': member.email or '',
                    'team': team.name,
                })

        faculty = [
            {'id': i.id, 'username': i.username, 'email': i.email or ''}
            for i in cohort.instructors.all().order_by('username')
        ]

        rounds = []
        for number in range(1, total + 1):
            if number < current:
                status = 'completed'
            elif number == current:
                status = 'active' if is_active else 'completed'
            else:
                status = 'upcoming'
            rounds.append({'number': number, 'status': status})

        return Response({
            'id': cohort.id,
            'name': cohort.name,
            'tier': cohort.tier,
            'status': 'active' if is_active else 'complete',
            'round': current,
            'total_rounds': total,
            'progress': round(current / total * 100) if current else 0,
            'teams': teams,
            'faculty': faculty,
            'students': students,
            'rounds': rounds,
            'deployment_status': cohort.deployment_status,
            'deployed_for_faculty_at': cohort.deployed_for_faculty_at.isoformat() if cohort.deployed_for_faculty_at else None,
            'deployed_for_students_at': cohort.deployed_for_students_at.isoformat() if cohort.deployed_for_students_at else None,
        })

    def delete(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        cohort.delete()
        return Response(status=204)
    
def _instructor_cohort_row(cohort):
    teams = list(Team.objects.filter(cohort=cohort).prefetch_related('members'))
    runs = Run.objects.filter(team__cohort=cohort)
    current = runs.aggregate(m=Max('current_week'))['m'] or 0
    is_active = runs.filter(status=RunStatus.IN_PROGRESS).exists()
    deployment = cohort.deployment_status
    total = ADMIN_TOTAL_ROUNDS
    if deployment == 'students' and not is_active and current >= total:
        run_status = 'completed'
    elif deployment == 'students' and current > 1:
        run_status = 'in_progress'
    else:
        run_status = 'ready'
    return {
        'id': cohort.id,
        'name': cohort.name,
        'tier': cohort.tier,
        'teams': len(teams),
        'students': sum(t.members.count() for t in teams),
        'round': current,
        'total_rounds': total,
        'progress': round(current / total * 100) if current else 0,
        'run_status': run_status,
        'needs_setup': deployment != 'students',
        'deployment_status': deployment,
        'deployed_for_faculty_at': cohort.deployed_for_faculty_at.isoformat() if cohort.deployed_for_faculty_at else None,
        'deployed_for_students_at': cohort.deployed_for_students_at.isoformat() if cohort.deployed_for_students_at else None,
        'created_at': cohort.created_at.isoformat() if cohort.created_at else None,
    }


class AdminDeployFacultyView(APIView):
    """Admin opens a simulation to its faculty."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        if not cohort.deployed_for_faculty_at:
            cohort.deployed_for_faculty_at = dj_timezone.now()
            cohort.save(update_fields=['deployed_for_faculty_at'])
        return Response(_simulation_row(cohort))


class InstructorSimulationsView(APIView):
    """The cohorts this instructor teaches, with deployment state."""

    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        cohorts = request.user.instructed_cohorts.all().order_by('name')
        return Response([_instructor_cohort_row(c) for c in cohorts])


class InstructorDeployStudentsView(APIView):
    """The assigned instructor opens a faculty-deployed simulation to students."""

    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id, instructors=request.user)
        if not cohort.deployed_for_faculty_at:
            return Response({'detail': 'This simulation has not been deployed to faculty yet.'}, status=409)
        if not cohort.deployed_for_students_at:
            cohort.deployed_for_students_at = dj_timezone.now()
            cohort.save(update_fields=['deployed_for_students_at'])
        return Response(_instructor_cohort_row(cohort))