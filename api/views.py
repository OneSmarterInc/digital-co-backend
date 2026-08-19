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

from advisor_agents.personas import ADVISORS
from advisors.agent_bridge import agent_key
from advisors.models import (
    AdvisorDefinition, AdvisorSession, Conversation, GroupSession, Message, MessageRole,
)
from advisors.services import (
    AdvisorService, GroupAdvisorService, MAX_GROUP_ADVISORS, MIN_GROUP_ADVISORS,
)
from core.models import (
    DEFAULT_ADVISOR_HOURLY_RATE, Cohort, Enrollment, Run, RunStatus, Team, Tier, User, UserRole,
)
from core.state import SCORE_DIMENSIONS
from engine.climax import generate_debrief
from help.services import HelpService
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


def run_for_user(user, cohort_id=None):
    """The student's run, optionally scoped to one cohort.

    A student may be enrolled in several simulations at once — one Team + Run per
    cohort, each with its own week and state. Passing cohort_id selects that
    sim's run, which is what keeps concurrent enrollments independent. Without it
    we fall back to the first run, preserving single-sim behavior. An invalid or
    non-numeric cohort_id resolves to no run rather than erroring."""
    qs = Run.objects.select_related('team__cohort').filter(team__members=user)
    if cohort_id not in (None, ''):
        try:
            cohort_id = int(cohort_id)
        except (TypeError, ValueError):
            return None
        qs = qs.filter(team__cohort_id=cohort_id)
    return qs.first()


def resolve_run(request):
    """Resolve the acting student's run for the cohort the request targets.

    The student app is per-cohort (URL /student/<cohortId>), so runtime calls
    carry the cohort id: ?cohort=<id> on GET, {"cohort": <id>} in the body on
    POST. This is the single choke point that makes multi-sim enrollment work;
    every student runtime view resolves its run through here."""
    cohort_id = request.query_params.get('cohort')
    if cohort_id in (None, '') and hasattr(request, 'data'):
        try:
            cohort_id = request.data.get('cohort')
        except Exception:
            cohort_id = None
    return run_for_user(request.user, cohort_id)


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
        run = resolve_run(request)
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
        run = resolve_run(request)
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
        run = resolve_run(request)
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
        run = resolve_run(request)
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
        run = resolve_run(request)
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
        run = resolve_run(request)
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

        run = resolve_run(request)
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


class GroupStartView(APIView):
    """Open a war-room round: 2-4 advisors in one shared thread for this week.

    POST {"active_advisors": ["diane_brandt", ...]} -> the new session. Starting
    again simply opens a fresh room; GroupConversationView returns the latest.
    Group chat is unbilled (no AdvisorSession), unlike one-on-one advisor chat.
    """

    def post(self, request):
        run = resolve_run(request)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        instance = get_or_create_week_instance(run)

        requested = request.data.get('active_advisors')
        if not isinstance(requested, list):
            return Response({'detail': 'active_advisors must be a list.'}, status=400)

        # Keep only real, active advisors that map onto the six-character cast,
        # de-duplicated, in the order the student picked them.
        valid = {d.key for d in AdvisorDefinition.objects.filter(active=True)}
        keys = []
        for key in dict.fromkeys(requested):
            if key in valid and agent_key(key) in ADVISORS and key not in keys:
                keys.append(key)

        if len(keys) < MIN_GROUP_ADVISORS:
            return Response(
                {'detail': f'Pick at least {MIN_GROUP_ADVISORS} advisors for a room.'}, status=400,
            )
        if len(keys) > MAX_GROUP_ADVISORS:
            return Response(
                {'detail': f'A room holds at most {MAX_GROUP_ADVISORS} advisors.', 'max': MAX_GROUP_ADVISORS},
                status=400,
            )

        session = GroupSession.objects.create(
            run=run, week_number=instance.week_number, active_advisors=keys,
        )
        return Response(serialize.group_session_json(session), status=201)


class GroupConversationView(APIView):
    """Read or post to the current week's war-room round.

    GET  -> {"session": <group>|null, "week_number": n}
    POST {"content": "..."} -> the updated group (runs the advisor cascade).
    """

    def _resolve(self, request):
        run = resolve_run(request)
        if not run:
            return no_run_response()
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked
        instance = get_or_create_week_instance(run)
        session = (
            GroupSession.objects
            .filter(run=run, week_number=instance.week_number)
            .order_by('-created_at', '-id')
            .first()
        )
        return run, instance, session

    def get(self, request):
        resolved = self._resolve(request)
        if isinstance(resolved, Response):
            return resolved
        _, instance, session = resolved
        return Response({
            'week_number': instance.week_number,
            'session': serialize.group_session_json(session) if session else None,
        })

    def post(self, request):
        resolved = self._resolve(request)
        if isinstance(resolved, Response):
            return resolved
        run, _, session = resolved
        if not session:
            return Response({'detail': 'Start a room before sending a message.'}, status=409)
        content = (request.data.get('content') or '').strip()
        if content:
            self._meter_group_session(request.user, run, session)
            GroupAdvisorService().respond(
                session=session,
                message=content,
                run_state=run.state,
                tier=run.team.cohort.tier,
            )
        session.refresh_from_db()
        return Response(serialize.group_session_json(session))

    @staticmethod
    def _meter_group_session(user, run, session):
        """Same hourly meter as a 1:1 advisor, priced for a room: one started hour
        costs the cohort rate once per advisor seated in it. The roster is fixed
        when the room is created, so the count can't drift mid-hour."""
        cohort = run.team.cohort
        now = dj_timezone.now()
        open_session = (
            AdvisorSession.objects
            .filter(group_session=session, student=user, started_at__gt=now - timedelta(hours=1))
            .order_by('-started_at')
            .first()
        )
        if open_session:
            open_session.last_activity_at = now
            open_session.save(update_fields=['last_activity_at'])
            return open_session
        enrollment = Enrollment.objects.filter(cohort=cohort, student=user).first()
        return AdvisorSession.objects.create(
            group_session=session,
            student=user,
            enrollment=enrollment,
            hourly_rate=cohort.advisor_hourly_rate or 0,
            advisor_count=max(1, len(session.active_advisors or [])),
        )


class InstructorQueueView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        cohorts = request.user.instructed_cohorts.all()
        # The per-simulation grading page passes ?cohort=<id> so an instructor
        # teaching several sims sees only that sim's queue; the cohort must still
        # be one they teach. Without it, the queue spans all their cohorts.
        cohort_id = request.query_params.get('cohort')
        if cohort_id:
            cohorts = cohorts.filter(id=cohort_id)
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
        rows = []
        for b in benchmarks:
            row = student_benchmark_payload(b)
            row['is_revealed'] = b.is_revealed
            rows.append(row)
        return Response(rows)

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


def _workspace_billing(simulations):
    """Roll the per-cohort billing (see instructor_api._billing) up to a
    workspace total for the admin billing screen. rates_configured is False when
    every cohort is free (no per-seat price and no advisor rate) — the UI shows a
    'set a rate to see charges' note rather than fabricated figures."""
    fields = ('total_billed', 'received', 'pending', 'advisor_billed',
              'advisor_hours', 'group_billed', 'group_hours',
              'paid_count', 'total_count')
    agg = {f: 0 for f in fields}
    rates_configured = False
    for sim in simulations:
        billing = sim['billing']
        for field in fields:
            agg[field] += billing.get(field, 0) or 0
        if (billing.get('price_per_student') or 0) > 0 or (billing.get('advisor_hourly_rate') or 0) > 0:
            rates_configured = True
    agg['seat_billed'] = agg['total_billed'] - agg['advisor_billed']
    agg['rates_configured'] = rates_configured
    return agg


class InstructorBenchmarkRevealView(APIView):
    """Flip a benchmark to revealed — the standings moment, on the
    instructor's cue rather than silently."""

    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, cohort_id, after_week):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        if not request.user.instructed_cohorts.filter(id=cohort.id).exists():
            return Response({'detail': 'Not your cohort.'}, status=403)
        benchmark = get_object_or_404(Benchmark, cohort=cohort, after_week=after_week)
        if not benchmark.is_revealed:
            benchmark.is_revealed = True
            benchmark.save(update_fields=['is_revealed'])
        return Response({'after_week': benchmark.after_week, 'is_revealed': True})


class AdminSimulationsView(APIView):
    """List every cohort as a 'simulation' (GET) or create one (POST)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # Lazy import: instructor_api imports from this module, so importing its
        # _billing at module load would be a circular import.
        from .instructor_api import _billing

        cohorts = list(Cohort.objects.all().order_by('id'))
        simulations = []
        for cohort in cohorts:
            row = _simulation_row(cohort)
            row['billing'] = _billing(cohort, list(Enrollment.objects.filter(cohort=cohort)))
            simulations.append(row)
        stats = {
            'total_games': len(simulations),
            'active': sum(1 for s in simulations if s['status'] == 'active'),
            'total_teams': sum(s['teams'] for s in simulations),
            'total_rounds': ADMIN_TOTAL_ROUNDS * len(simulations),
        }
        return Response({
            'stats': stats,
            'simulations': simulations,
            'billing': _workspace_billing(simulations),
        })

    def post(self, request):
        # Every field is validated and reported per-field. This used to accept
        # almost anything: a blank tier silently became UNDERGRAD, a cleared
        # team count became 0 (a simulation with no firms), an unparseable date
        # became None, and out-of-range numbers were silently clamped. An admin
        # got a created simulation that quietly wasn't what they typed.
        errors = {}

        name = (request.data.get('name') or '').strip()
        if not name:
            errors['name'] = 'Give the simulation a name.'
        elif len(name) > 255:
            errors['name'] = 'Keep the name under 255 characters.'
        elif Cohort.objects.filter(name__iexact=name).exists():
            errors['name'] = 'A simulation with that name already exists.'

        tier = request.data.get('tier')
        if tier not in (Tier.UNDERGRAD, Tier.GRADUATE):
            errors['tier'] = 'Choose Undergraduate or Graduate.'

        def required_int(key, label, lo, hi, alias=None):
            """A number the admin must supply, inside its range — never clamped
            or defaulted silently, because both hide a typo.

            Errors are keyed by the name the caller actually used, so the form
            can attach the message to the field the admin is looking at. The
            frontend says "days_per_round" where the model says "days_per_week";
            reporting under the model's name left that error orphaned."""
            supplied = key if key in request.data else (
                alias if alias and alias in request.data else (alias or key)
            )
            raw = request.data.get(key, request.data.get(alias) if alias else None)
            if raw in (None, ''):
                errors[supplied] = f'{label} is required.'
                return None
            try:
                value = int(raw)
            except (TypeError, ValueError):
                errors[supplied] = f'{label} must be a whole number.'
                return None
            if not lo <= value <= hi:
                errors[supplied] = f'{label} must be between {lo} and {hi}.'
                return None
            return value

        team_count = required_int('teams', 'Number of firms', 1, 20)
        # The frontend says "rounds", so days_per_round is accepted as an alias.
        days_per_week = required_int('days_per_week', 'Round length', 1, 60, alias='days_per_round')
        team_size = required_int('team_size', 'Firm size', 1, 12)
        enrollment_capacity = required_int('enrollment_capacity', 'Enrollment capacity', 1, 1000)
        price_per_student = required_int('price_per_student', 'Price per student', 0, 100000)
        advisor_hourly_rate = required_int('advisor_hourly_rate', 'Advisor rate', 0, 100000)

        if team_count and team_size and enrollment_capacity:
            if team_count * team_size > enrollment_capacity:
                errors['enrollment_capacity'] = (
                    f'{team_count} firms of {team_size} needs at least '
                    f'{team_count * team_size} seats.'
                )

        timezone = (request.data.get('timezone') or '').strip()
        if not timezone:
            errors['timezone'] = 'Choose a time zone.'

        raw_start = (request.data.get('start_date') or '').strip()
        # parse_date returns None for a malformed string but *raises* for a
        # well-formed impossible one ("2026-13-45"), which would 500 the create.
        try:
            start_date = parse_date(raw_start) if raw_start else None
        except ValueError:
            start_date = None
        if not raw_start:
            errors['start_date'] = 'Set a start date — the round calendar is built from it.'
        elif start_date is None:
            errors['start_date'] = 'That start date is not a valid date.'

        if errors:
            return Response(
                {'detail': 'Some fields need attention.', 'errors': errors}, status=400,
            )

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

        for index in range(team_count):
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

class HelpAskView(APIView):
    """The 'Something else' box in the help window.

    Deliberately thin: it takes a question, hands it to the starved help channel,
    and returns the answer. Nothing is stored — see help/services.py — and the
    channel's prompt carries no scenario content, so there is nothing here for a
    student to extract by asking cleverly.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'detail': 'Ask a question first.'}, status=400)
        try:
            answer = HelpService().answer(question)
        except Exception:
            return Response(
                {'detail': "The help channel isn't reachable right now. The FAQ above covers most of it."},
                status=503,
            )
        return Response({'answer': answer})
