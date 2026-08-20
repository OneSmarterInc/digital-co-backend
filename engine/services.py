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
    week_instance.run.save()

    score = ScoreRecord.objects.create(
        week_instance=week_instance,
        auto_components={
            'scores': auto.normalized_scores(),
            'trap_flags': auto.trap_flags,
            'components': auto.components,
        },
        **auto.normalized_scores(),
    )
    week_instance.submission = submission
    week_instance.score_record = score
    week_instance.status = WeekInstanceStatus.SUBMITTED
    week_instance.save()
    return submission


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
