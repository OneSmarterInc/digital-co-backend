"""Student-facing API endpoints.

Backs the student home screen: after login a student sees every cohort they are
enrolled in, with round progress, firm assignment, and billing state. Follows the
same conventions as instructor_api (JWT auth, plain Response payloads) and reuses
its helpers so the "rounds" and "firms" language stays consistent across both
sides of the app. Nothing here touches the scoring engine.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Count, Sum

from advisors.models import BILLED, AdvisorSession
from core.models import Enrollment, Run

from .instructor_api import _firm_numbering, _rounds
from .views import ADMIN_TOTAL_ROUNDS, resolve_run


def _run_completed(run):
    if run is None:
        return False
    from core.models import RunStatus
    from weeks.models import WeekInstance, WeekInstanceStatus
    if run.status == RunStatus.COMPLETE:
        return True
    return WeekInstance.objects.filter(
        run=run,
        week_number=14,
        status__in=[WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED],
    ).exists()


class StudentSimulationsView(APIView):
    """Every cohort the requesting student is enrolled in.

    One row per enrollment. The round pointer prefers the student's own team run
    (their firm may be ahead of or behind the cohort), and falls back to the
    cohort-wide maximum when they have no firm yet, so the schedule still reads
    sensibly before the instructor places them.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollments = (
            Enrollment.objects.filter(student=request.user)
            .select_related('cohort', 'team')
            .order_by('-enrolled_at')
        )
        rows = []
        for e in enrollments:
            cohort = e.cohort

            current = None
            own_run = None
            if e.team_id:
                own_run = Run.objects.filter(team_id=e.team_id).first()
                current = own_run.current_week if own_run else None
            if current is None:
                current = max(
                    (r.current_week for r in Run.objects.filter(team__cohort=cohort)),
                    default=1,
                ) or 1

            usage = (
                AdvisorSession.objects
                .for_cohort(cohort)
                .filter(student=request.user)
                .aggregate(hours=Count('id'), due=Sum(BILLED))
            )

            _, numbering = _firm_numbering(cohort)
            number = numbering.get(e.team_id) if e.team_id else None

            rows.append({
                'id': cohort.id,
                'enrollment_id': e.id,
                'name': cohort.name,
                'tier': cohort.tier,
                'deployment_status': cohort.deployment_status,
                'current_round': current,
                'total_rounds': ADMIN_TOTAL_ROUNDS,
                # True only when the run is actually finished: marked COMPLETE
                # or Week 14 submitted. current_round == total_rounds is NOT
                # completion — that's just the final round being played.
                'completed': _run_completed(own_run),
                'start_date': cohort.start_date.isoformat() if cohort.start_date else None,
                'days_per_round': cohort.days_per_week,
                'firm': e.team.name if e.team else None,
                'firm_index': (number - 1) if number else None,
                'paid': e.paid,
                'blocked': e.blocked,
                'advisor_hourly_rate': cohort.advisor_hourly_rate or 0,
                'advisor_hours': usage['hours'] or 0,
                'advisor_due': usage['due'] or 0,
                'rounds': _rounds(cohort, current),
            })
        return Response(rows)


class MyProfileView(APIView):
    """Read and complete the signed-in user's profile.

    Backs the first-login gate on the student home screen: when a student was
    created from an email invite they have no name yet, so the frontend shows a
    profile form and saves here before revealing the cohort list. Works for any
    authenticated user; PATCH and POST are equivalent.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(self._payload(request.user))

    def patch(self, request):
        user = request.user
        first = str(request.data.get('first_name', '')).strip()
        last = str(request.data.get('last_name', '')).strip()
        if not first:
            return Response({'detail': 'First name is required.'}, status=400)
        if len(first) > 150 or len(last) > 150:
            return Response({'detail': 'Names must be 150 characters or fewer.'}, status=400)
        user.first_name = first
        user.last_name = last
        user.save(update_fields=['first_name', 'last_name'])
        return Response(self._payload(user))

    def post(self, request):
        return self.patch(request)

    @staticmethod
    def _payload(user):
        return {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'name_set': bool((user.first_name or '').strip()),
        }



def _benchmark_state(run):
    """What a student may know about standings at a checkpoint round.

    Two gates stand between a graded round and a student seeing the table, and
    they answer different questions:

    1. `benchmark_ready` — is the table *correct*? Standings rank firms against
       each other, so a firm that is merely ungraded ranks exactly like one that
       played badly. An incomplete table is not provisional, it is wrong.
    2. `revealed_at` — is this the *moment*? The reveal is a teaching device.
       The Week 14 note asks for it after teams have read their own debriefs,
       "so the standings land as epilogue rather than verdict".

    Saying nothing at all fails the student either way: at a checkpoint they see
    an empty screen and cannot tell "not yet" from "broken", which produces the
    very questions the withholding was meant to prevent.

    What is never disclosed is *which* firms are outstanding, or how many. Which
    firm is behind on grading is not a student's business, and a count is a
    small leak that compounds fast in a cohort that talks to each other.
    """
    from scoring.config import BENCHMARK_PHASE_WEEKS
    from scoring.models import Benchmark
    from scoring.services import benchmark_ready

    cohort = run.team.cohort
    reached = [w for w in BENCHMARK_PHASE_WEEKS if w <= run.current_week]
    if not reached:
        return None

    after_week = max(reached)
    benchmark = Benchmark.objects.filter(cohort=cohort, after_week=after_week).first()
    if benchmark is None:
        # Not graded for anyone yet. That is not "pending", it simply has not
        # happened, and calling it pending would be its own kind of noise.
        return None
    if not benchmark_ready(cohort, after_week):
        return {'after_week': after_week, 'status': 'pending'}
    if not benchmark.is_revealed:
        return {'after_week': after_week, 'status': 'awaiting_release'}
    return {'after_week': after_week, 'status': 'published'}


def _student_standings(run):
    """Every benchmark this student may read, oldest first.

    All of them, not just the latest: the Week 8 discussion turns on comparing
    against Benchmark 1, and a table a student saw once in class is useless if
    they cannot look it up again in week nine.
    """
    from scoring.models import Benchmark
    from scoring.services import benchmark_ready, student_benchmark_payload

    cohort = run.team.cohort
    rows = []
    for benchmark in Benchmark.objects.filter(cohort=cohort).order_by('after_week'):
        if not benchmark.is_revealed:
            continue
        if not benchmark_ready(cohort, benchmark.after_week):
            # Revealed earlier, then a firm was added or re-opened. Correctness
            # outranks the fact that it was once released.
            continue
        payload = student_benchmark_payload(benchmark)
        payload['your_firm'] = run.team.name
        rows.append(payload)
    return rows


class StudentFirmView(APIView):
    """Who is in the requesting student's firm.

    A team commits one decision a week and is told to split the advisors between
    them, which is impossible if you do not know who "them" is. Students invited
    by email land in a firm without ever being told who else is in it.

    Scoped to the caller's own firm: this returns nothing about any other team,
    so it cannot be used to map the cohort. Names only — an address is the
    instructor's to share, not something the roster should hand out.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.models import Team

        cohort_id = request.query_params.get('cohort')
        enrollment = (
            Enrollment.objects
            .select_related('team', 'cohort')
            .filter(student=request.user, **({'cohort_id': cohort_id} if cohort_id else {}))
            .first()
        )
        if enrollment is None:
            return Response({'detail': 'You are not enrolled in this simulation.'}, status=404)

        team = enrollment.team
        if team is None:
            # Placed later by the instructor. Say so plainly rather than
            # returning an empty roster, which reads as "your firm is empty".
            return Response({
                'firm': None,
                'firm_index': None,
                'members': [],
                'awaiting_placement': True,
            })

        _, numbering = _firm_numbering(enrollment.cohort)
        number = numbering.get(team.id)

        members = []
        for member in team.members.all().order_by('first_name', 'last_name', 'username'):
            name = (member.get_full_name() or '').strip()
            members.append({
                'id': member.id,
                # Someone invited by email who has not completed their profile
                # has no name yet. Their username is their address, so showing
                # it as a fallback would publish the address to the team.
                'name': name or 'Joining soon',
                'named': bool(name),
                'is_you': member.id == request.user.id,
            })

        return Response({
            'firm': team.name,
            'firm_index': (number - 1) if number else None,
            'members': members,
            'awaiting_placement': False,
        })


class StudentPerformanceView(APIView):
    """Past-round performance for the requesting student's firm.

    Returns only weeks whose grade is instructor-final (status SCORED), with
    the four dimension scores and totals. Deliberately excludes the engine's
    auto_components and trap flags: those reveal the detection machinery, and
    exposing them mid-run would let teams reverse-engineer the traps. Scores
    are per firm, so every member of a team sees the same history.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from weeks.models import WeekInstance, WeekInstanceStatus

        run = resolve_run(request)
        if run is None:
            return Response({'detail': 'No run is assigned to this user.'}, status=404)
        from .views import blocked_response
        blocked = blocked_response(request.user, run)
        if blocked:
            return blocked

        instances = (
            WeekInstance.objects
            .filter(run=run, status=WeekInstanceStatus.SCORED)
            .select_related('score')
            .order_by('week_number')
        )
        rows = []
        for instance in instances:
            score = getattr(instance, 'score', None)
            if score is None:
                continue
            dims = score.dimension_scores()
            rows.append({
                'week_number': instance.week_number,
                'scores': dims,
                'total': sum(dims.values()),
                'graded_at': score.graded_at.isoformat() if score.graded_at else None,
                # The four numbers explain nothing on their own; this is what a
                # student is actually meant to learn from.
                'feedback': score.feedback,
            })
        best = max((r['total'] for r in rows), default=0)

        return Response({
            'weeks': rows,
            'graded_count': len(rows),
            'average': round(sum(r['total'] for r in rows) / len(rows), 1) if rows else 0,
            'best': best,
            'benchmark': _benchmark_state(run),
            'standings': _student_standings(run),
        })