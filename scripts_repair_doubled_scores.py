"""One-shot corrective pass for the grade double-count.

The grading modal pre-filled the instructor's adjustment boxes with the engine's
own numbers, and finalize_score adds the adjustment on top of the engine score.
So for every record graded through that path:

    recorded = auto + submitted,  where  submitted = auto + real_adjustment

The real adjustment is therefore (recorded - 2*auto), and the correct value is:

    corrected = auto + real_adjustment = recorded - auto

finalize_score also pushed the recorded value into run.state['accumulated_scores'],
so each run's totals are over by exactly the auto score of each affected record.

Each corrected record is stamped with auto_components['double_count_corrected']
so the pass is idempotent — re-running it is a no-op rather than a second
subtraction. Do not remove that guard.

Run with --apply to write. Without it, this only reports.

    .venv/bin/python manage.py shell -c "exec(open('scripts_repair_doubled_scores.py').read())"
"""
import sys

from core.state import SCORE_DIMENSIONS
from scoring.models import ScoreRecord

APPLY = '--apply' in sys.argv

runs_delta = {}
fixed = 0

for record in ScoreRecord.objects.select_related('week_instance__run').filter(graded_at__isnull=False):
    # Already put right by an earlier run of this script.
    if record.auto_components.get('double_count_corrected'):
        continue
    auto = record.auto_components.get('scores', {})
    recorded = {d: getattr(record, d) for d in SCORE_DIMENSIONS}
    # Only records where the engine actually proposed something could be doubled.
    if not any(auto.get(d) for d in SCORE_DIMENSIONS):
        continue
    corrected = {d: recorded[d] - int(auto.get(d, 0)) for d in SCORE_DIMENSIONS}
    if corrected == recorded:
        continue
    print(f'record {record.id} wk{record.week_instance.week_number} '
          f'{record.week_instance.run.team.name}: {recorded} -> {corrected}')
    fixed += 1
    run = record.week_instance.run
    delta = runs_delta.setdefault(run.id, {d: 0 for d in SCORE_DIMENSIONS})
    for d in SCORE_DIMENSIONS:
        delta[d] += int(auto.get(d, 0))
    if APPLY:
        for d, value in corrected.items():
            setattr(record, d, value)
        record.auto_components['double_count_corrected'] = True
        record.save(update_fields=list(SCORE_DIMENSIONS) + ['auto_components'])

from core.models import Run
for run_id, delta in runs_delta.items():
    run = Run.objects.get(id=run_id)
    before = dict(run.state['accumulated_scores'])
    after = {d: before.get(d, 0) - delta[d] for d in SCORE_DIMENSIONS}
    print(f'run {run_id} ({run.team.name}) accumulated: {before} -> {after}')
    if APPLY:
        run.state['accumulated_scores'].update(after)
        run.save(update_fields=['state'])

print(f'\n{fixed} score records, {len(runs_delta)} runs '
      f'{"CORRECTED" if APPLY else "would be corrected (dry run)"}')
