from django.utils import timezone

from core.state import SCORE_DIMENSIONS
from engine.climax import resolve_endgame
from weeks.models import WeekInstanceStatus
from weeks.registry import registry

from .config import (
    BENCHMARK_PHASE_WEEKS,
    BENCHMARK_COHERENCE_DRIFT_WEIGHT,
    BENCHMARK_GATE_RANK_FACTOR,
    DATA_ADVANTAGE_BENCHMARK_POINTS,
    TRUST_BENCHMARK_POINTS,
)
from .models import Benchmark


def merge_score_components(auto_scores: dict, instructor_scores: dict) -> dict:
    merged = {}
    for dimension in SCORE_DIMENSIONS:
        merged[dimension] = int(auto_scores.get(dimension, 0)) + int(instructor_scores.get(dimension, 0))
    return merged


def finalize_score(
    score_record, *, instructor_scores=None, instructor_components=None,
    graded_by=None, feedback=None,
):
    """Record a grade, and make re-grading safe.

    Grading adds the merged score to the run's running total, so saving a grade
    twice would count it twice. Each record therefore remembers what it last
    contributed (applied_scores) and that contribution is reversed before the new
    one is applied — an edit overwrites rather than accumulates.

    The week's own state update (flags, through-lines, relationships) runs only
    on the first grading. Those effects follow from the decision, not the score,
    and are not written to be applied twice.
    """
    instructor_scores = instructor_scores or {}
    regrade = score_record.graded_at is not None
    # Records graded before applied_scores existed still carry their contribution
    # in the dimension columns, which is what was added at the time.
    previously_applied = (
        dict(score_record.applied_scores) if score_record.applied_scores
        else (score_record.dimension_scores() if regrade else {})
    )

    auto_scores = score_record.auto_components.get('scores', {})
    merged = merge_score_components(auto_scores, instructor_scores)
    for dimension, value in merged.items():
        setattr(score_record, dimension, value)
    score_record.instructor_components = instructor_components or score_record.instructor_components
    score_record.graded_by = graded_by or score_record.graded_by
    score_record.graded_at = timezone.now()
    score_record.applied_scores = merged
    if feedback is not None:
        score_record.feedback = feedback
    score_record.save()

    week_instance = score_record.week_instance
    state = week_instance.run.state
    for dimension, value in previously_applied.items():
        state['accumulated_scores'][dimension] -= value
    for dimension, value in score_record.dimension_scores().items():
        state['accumulated_scores'][dimension] += value
    module = registry.get(week_instance.week_number)
    if not regrade:
        state = module.finalize_state_update(score_record, state)
    week_instance.run.state = state
    week_instance.status = WeekInstanceStatus.SCORED
    week_instance.score_record = score_record
    week_instance.run.save()
    week_instance.save()

    if week_instance.week_number == 14:
        week_instance.run.tier_outcome = week_instance.run.state.get('flags', {}).get('endgame_tier') or resolve_endgame(week_instance.run.state)
        week_instance.run.status = 'COMPLETE'
        week_instance.run.save()
    if week_instance.week_number in BENCHMARK_PHASE_WEEKS:
        # Always computed, never gated here. Week 5 has a hard dependency on a
        # Benchmark existing for the cohort (engine.services checks
        # 'benchmarks.latest'), so withholding computation would freeze every
        # firm at Week 5 until the slowest one was graded — and freeze them
        # permanently if a firm never submits. Whether the standings are fit to
        # *show* is a separate question, answered by benchmark_ready().
        compute_benchmark(week_instance.run.team.cohort, week_instance.week_number)
    return score_record


def compute_endgame_outcome(run_state: dict):
    return resolve_endgame(run_state)


def benchmark_firms(cohort):
    """The firms a benchmark ranks: those taking part.

    A firm is created with a run already attached, so an unfilled one would
    otherwise sit permanently ungraded and hold the whole cohort's standings
    hostage — as well as appearing in them on zero.

    Taking part means having members, or having played at least one round.
    The second half matters: a firm whose students were moved out mid-term has
    still earned its place in the table.
    """
    from weeks.models import WeekInstance

    played = set(
        WeekInstance.objects
        .filter(run__team__cohort=cohort)
        .values_list('run__team_id', flat=True)
    )
    return [
        team for team in cohort.teams.select_related('run').prefetch_related('members')
        if getattr(team, 'run', None) is not None
        and (team.members.exists() or team.id in played)
    ]


def benchmark_pending(cohort, after_week: int):
    """Firms still owing a grade for this round. Empty list means ready."""
    from weeks.models import WeekInstance

    graded = set(
        WeekInstance.objects
        .filter(
            run__team__cohort=cohort,
            week_number=after_week,
            status=WeekInstanceStatus.SCORED,
        )
        .values_list('run__team_id', flat=True)
    )
    return [team for team in benchmark_firms(cohort) if team.id not in graded]


def benchmark_ready(cohort, after_week: int) -> bool:
    """True when the standings for this round are fit to show.

    Standings rank firms against each other on accumulated score, so a firm
    that is merely *not yet graded* has a smaller total and is indistinguishable
    from one that played badly. A partially graded table is not a provisional
    result — it is a wrong one, so it is withheld rather than captioned.

    A cohort with no playing firms is never ready: there is nothing to rank,
    and an empty table reads as a result rather than an absence.
    """
    firms = benchmark_firms(cohort)
    if not firms:
        return False
    return not benchmark_pending(cohort, after_week)


def compute_benchmark(cohort, after_week: int):
    if after_week not in BENCHMARK_PHASE_WEEKS:
        raise ValueError(f'Benchmarks can only be computed after weeks {BENCHMARK_PHASE_WEEKS}.')
    standings = []
    for team in benchmark_firms(cohort):
        run = team.run
        total = sum(run.state['accumulated_scores'].values())
        trust_points = _phase_trust_points(run.state, after_week)
        gate_factor = _gate_rank_factor(run.state, after_week)
        drift_penalty = _coherence_drift_penalty(run.state, after_week)
        benchmark_score = round(((total + trust_points) * gate_factor) - drift_penalty, 2)
        tier_outcome = run.tier_outcome
        if after_week == 14 and not tier_outcome:
            tier_outcome = resolve_endgame(run.state)
        standings.append({
            'team_id': team.id,
            'team_name': team.name,
            'total_score': total,
            'benchmark_score': benchmark_score,
            'trust_points': trust_points,
            'drift_penalty': drift_penalty,
            'gate_factor': gate_factor,
            'visible_strengths': _visible_strengths(run.state, total, after_week),
            'visible_weaknesses': _visible_weaknesses(run.state, after_week, gate_factor, drift_penalty),
            'factors': _benchmark_factors(after_week),
            'tier_outcome': tier_outcome,
        })
    standings.sort(key=lambda row: (row['benchmark_score'], row['total_score']), reverse=True)
    for index, row in enumerate(standings, start=1):
        row['rank'] = index
    benchmark, _ = Benchmark.objects.update_or_create(
        cohort=cohort,
        after_week=after_week,
        defaults={'standings': standings},
    )
    return benchmark


def _benchmark_factors(after_week):
    if after_week in (4, 8):
        return ['accumulated_score']
    if after_week == 11:
        return ['accumulated_score', 'trust']
    return ['accumulated_score', 'trust', 'resolved_tier']


def _phase_trust_points(state, after_week):
    if after_week not in (11, 14):
        return 0
    flags = state.get('flags', {})
    return (
        TRUST_BENCHMARK_POINTS.get(flags.get('trust_state'), 0)
        + DATA_ADVANTAGE_BENCHMARK_POINTS.get(flags.get('data_advantage'), 0)
    )


def _gate_rank_factor(state, after_week):
    if after_week == 8:
        return 1
    if after_week >= 4 and state['gates']['budget_credibility']['state'] == 'closed':
        return BENCHMARK_GATE_RANK_FACTOR
    return 1


def _coherence_drift_penalty(state, after_week):
    if after_week == 8:
        return 0
    if after_week < 4:
        return 0
    return BENCHMARK_COHERENCE_DRIFT_WEIGHT * len(state['through_lines']['coherence']['drift_events'])


def _visible_strengths(state, total, after_week):
    strengths = []
    if total > 0:
        strengths.append('Positive accumulated execution record')
    if state['relationships'].get('reinhardt', 0) > 0:
        strengths.append('Improving financial credibility')
    if state['relationships'].get('fischer', 0) > 0 and after_week >= 4:
        strengths.append('Engineering partnership strengthened')
    return strengths


def _visible_weaknesses(state, after_week, gate_factor, drift_penalty):
    weaknesses = []
    if gate_factor < 1:
        weaknesses.append('Budget credibility pressure affected standing')
    if drift_penalty:
        weaknesses.append('Early coherence drift affected standing')
    if state['relationships'].get('reinhardt', 0) < 0:
        weaknesses.append('Financial credibility weakened')
    return weaknesses


def student_benchmark_payload(benchmark):
    return {
        'after_week': benchmark.after_week,
        'standings': [
            {
                'rank': row['rank'],
                'team_name': row['team_name'],
                'total_score': row['total_score'],
                'benchmark_score': row['benchmark_score'],
                'visible_strengths': row.get('visible_strengths', []),
                'visible_weaknesses': row.get('visible_weaknesses', []),
                'tier_outcome': row.get('tier_outcome') if benchmark.after_week == 14 else None,
            }
            for row in benchmark.standings
        ],
    }


def reveal_benchmark(benchmark):
    benchmark.revealed_at = timezone.now()
    benchmark.save(update_fields=['revealed_at'])
    return benchmark
