"""Generate briefing preambles for rounds that are already open.

Normally a preamble is written once, at the moment a round opens, and a round
already in flight never gets one — retro-generating text for a briefing students
have read and acted on would change the page under them mid-round. That rule
stays; `view_briefing` is untouched.

This command is the deliberate exception, for a test simulation where nothing is
at stake and the point is to see the feature work. It names the cohort
explicitly and refuses to run across everything, so it cannot be pointed at a
live cohort by accident.

    python manage.py backfill_preambles --all --dry-run
    python manage.py backfill_preambles --all
    python manage.py backfill_preambles --cohort Test-Grad --round 2 --force
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from briefing.services import generate_preamble
from core.models import Cohort
from weeks.models import WeekInstance, WeekInstanceStatus

# Scored rounds are history: the firm has read the briefing, submitted against
# it and been graded. Only rounds still being played are eligible.
OPEN_STATUSES = (WeekInstanceStatus.BRIEFING, WeekInstanceStatus.CONSULTATION)


class Command(BaseCommand):
    help = 'Generate preambles for open rounds in one named cohort.'

    def add_arguments(self, parser):
        parser.add_argument('--cohort', default=None, help='Exact cohort name.')
        parser.add_argument(
            '--all', action='store_true', dest='all_cohorts',
            help='Every cohort with an open round. Must be given explicitly.',
        )
        parser.add_argument('--round', type=int, default=None, help='Limit to one round number.')
        parser.add_argument('--firm', default=None, help='Limit to one firm name.')
        parser.add_argument(
            '--force', action='store_true',
            help='Regenerate even where a preamble already exists.',
        )
        parser.add_argument(
            '--unread-only', action='store_true', dest='unread_only',
            help='Skip rounds the firm has already opened, so nothing changes mid-decision.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be generated without writing or calling the model.',
        )

    def handle(self, *args, **opts):
        ok, warn, bad = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        if bool(opts['cohort']) == bool(opts['all_cohorts']):
            raise CommandError('Give either --cohort <name> or --all, and not both.')

        if opts['all_cohorts']:
            cohort = None
            scope = 'every cohort'
        else:
            cohort = Cohort.objects.filter(name=opts['cohort']).first()
            if cohort is None:
                names = ', '.join(Cohort.objects.values_list('name', flat=True)) or '(none)'
                raise CommandError(f'No cohort named {opts["cohort"]!r}. Cohorts: {names}')
            scope = cohort.name

        instances = (
            WeekInstance.objects
            .filter(status__in=OPEN_STATUSES)
            .select_related('run__team__cohort')
            .order_by('run__team__cohort__name', 'run__team__name', 'week_number')
        )
        if cohort is not None:
            instances = instances.filter(run__team__cohort=cohort)
        if opts['round']:
            instances = instances.filter(week_number=opts['round'])
        if opts['firm']:
            instances = instances.filter(run__team__name=opts['firm'])

        instances = list(instances)
        if not instances:
            self.stdout.write(warn(f'Nothing open to backfill in {scope}.'))
            return

        # A round the firm has already opened is the one case the no-backfill
        # rule exists for: adding a paragraph above a briefing somebody read
        # yesterday changes the page under them mid-decision. Not blocked, but
        # never silent — the operator should know which ones those are.
        already_read = [i for i in instances if i.briefing_viewed_at]

        self.stdout.write(f'\n{scope} — {len(instances)} open round(s)\n')
        if already_read and not opts['unread_only']:
            self.stdout.write(warn(
                f'  {len(already_read)} of these have already been read by the firm. '
                'They will change mid-round. Use --unread-only to skip them.\n'
            ))
        if opts['unread_only']:
            instances = [i for i in instances if not i.briefing_viewed_at]
            self.stdout.write(f'  --unread-only: {len(instances)} round(s) not yet opened\n')

        written = skipped = failed = 0
        last_cohort = None

        for instance in instances:
            this_cohort = instance.run.team.cohort.name
            if cohort is None and this_cohort != last_cohort:
                self.stdout.write(f'\n  {this_cohort}')
                last_cohort = this_cohort
            seen = ' (already read)' if instance.briefing_viewed_at else ''
            label = f'{instance.run.team.name} round {instance.week_number}{seen}'

            if instance.preamble and not opts['force']:
                self.stdout.write(f'  {label}: already has one, leaving it (--force to replace)')
                skipped += 1
                continue

            if opts['dry_run']:
                self.stdout.write(f'  {label}: would generate')
                continue

            text, problem = generate_preamble(instance.run, instance.week_number)
            if not text:
                # Same silent-failure contract as the live path: the round is
                # perfectly playable without one. Reported here because someone
                # is watching, unlike at round open.
                self.stdout.write(bad(f'  {label}: no preamble — {problem}'))
                failed += 1
                continue

            instance.preamble = text
            instance.preamble_problem = ''
            instance.preamble_generated_at = timezone.now()
            instance.save(update_fields=[
                'preamble', 'preamble_problem', 'preamble_generated_at', 'updated_at',
            ])
            written += 1
            self.stdout.write(ok(f'  {label}: written'))
            self.stdout.write(f'      {text[:150]}{"…" if len(text) > 150 else ""}')

        if opts['dry_run']:
            self.stdout.write(warn('\nDry run — nothing was written.\n'))
        else:
            self.stdout.write(f'\nwritten {written} · skipped {skipped} · failed {failed}\n')
