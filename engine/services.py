from django.db import transaction
from django.utils import timezone

from scoring.models import Benchmark, ScoreRecord
from core.state import FLAG_CATALOG
from briefing.services import ensure_preamble
from weeks.models import Submission, WeekInstance, WeekInstanceStatus
from weeks.registry import registry


class InvalidTransition(ValueError):
    pass


def get_or_create_week_instance(run, week_number=None):
    week_number = week_number or run.current_week
    instance, _ = WeekInstance.objects.get_or_create(
        run=run,
        week_number=week_number,
        defaults={'status': WeekInstanceStatus.BRIEFING},
    )
    return instance


def view_briefing(run, *, week_number=None):
    instance = get_or_create_week_instance(run, week_number)
    if instance.status != WeekInstanceStatus.BRIEFING:
        return instance
    instance.briefing_viewed_at = timezone.now()
    instance.status = WeekInstanceStatus.CONSULTATION
    instance.save(update_fields=['briefing_viewed_at', 'status', 'updated_at'])
    # The firm-aware opening is written once, here, at the moment the round
    # opens. ensure_preamble never raises: a briefing renders without it rather
    # than not at all.
    ensure_preamble(instance)
    return instance


@transaction.atomic
def submit_week(week_instance, *, structured_payload, deliverable_text='', submitted_by=None):
    if week_instance.status not in (WeekInstanceStatus.BRIEFING, WeekInstanceStatus.CONSULTATION):
        raise InvalidTransition('Only briefing or consultation weeks can be submitted.')

    module = registry.get(week_instance.week_number)
    validate_state_dependencies(week_instance.run, module.reads_state())
    submission = Submission.objects.create(
        week_instance=week_instance,
        structured_payload=structured_payload,
        deliverable_text=deliverable_text,
        submitted_by=submitted_by,
    )
    auto = module.score_auto(submission, week_instance.run.state)
    week_instance.run.state = module.apply_state_update(submission, auto, week_instance.run.state)
    _record_hold(week_instance.run.state, week_instance.week_number, auto)
    week_instance.run.save()

    scores = dict(auto.normalized_scores())

    score = ScoreRecord.objects.create(
        week_instance=week_instance,
        auto_components={
            'scores': scores,
            'trap_flags': auto.trap_flags,
            'components': auto.components,
        },
        **scores,
    )
    week_instance.submission = submission
    week_instance.score_record = score
    week_instance.status = WeekInstanceStatus.SUBMITTED
    week_instance.save()

    # Deliverable quality is the one dimension no week module produces, so it is
    # proposed here from the writing itself. Kept outside the transaction-
    # critical path above and applied to the saved record: a model that is slow
    # or down must never stop a submission being recorded.
    _propose_deliverable_quality(score)
    return submission


def _propose_deliverable_quality(score_record):
    """Fill in the engine's read of the written deliverable.

    Logged in full — score and reasoning — separately from the number, so the
    proposal can be compared against the instructor's own judgement before it is
    trusted. Silent on failure: the record keeps its zero and the instructor
    types a number, exactly as before this existed.
    """
    from feedback.quality import propose_quality

    value, why, problem = propose_quality(score_record)
    components = score_record.auto_components
    components['deliverable_quality_proposal'] = {
        'score': value,
        'why': why,
        'problem': problem,
    }
    if value:
        components['scores']['deliverable_quality'] = value
        score_record.deliverable_quality = value
    score_record.auto_components = components
    score_record.save(update_fields=['auto_components', 'deliverable_quality'])


def _record_hold(state, week_number, auto):
    """Log a round where the firm held its line, for the Week 13 arc.

    Recorded centrally rather than in each week module, because the rule is the
    same everywhere: positive coherence for the round means the decision sat on
    the axis the anchor was stated on. Weeks whose options are defensible under
    either anchor score zero and record nothing, which is what keeps Week 3 out
    of it.

    The magnitude is not carried through — the arc weights every hold at one,
    against two to four for a drift, so holding accumulates quietly.
    """
    coherence = state.get('through_lines', {}).get('coherence')
    if coherence is None:
        return
    if auto.scores.get('coherence', 0) <= 0:
        return
    coherence.setdefault('hold_events', []).append({'week': week_number, 'weight': 'hold'})


def validate_state_dependencies(run, dependencies):
    state = run.state
    for dependency in dependencies:
        if dependency == 'benchmarks.latest':
            if not Benchmark.objects.filter(cohort=run.team.cohort).exists():
                raise InvalidTransition('Missing required state dependency: benchmarks.latest')
            continue
        current = state
        parts = dependency.split('.')
        for index, part in enumerate(parts):
            if index == 1 and parts[0] == 'flags' and part in FLAG_CATALOG and part not in current:
                break
            if not isinstance(current, dict) or part not in current:
                raise InvalidTransition(f'Missing required state dependency: {dependency}')
            current = current[part]
    return True
