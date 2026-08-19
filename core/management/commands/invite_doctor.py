"""Diagnose why an invite or registration link is being rejected.

Run this ON THE MACHINE THAT SERVES THE API, because the whole class of failure
here is "the token exists, but not in the database being asked".

    python manage.py invite_doctor                 # environment only
    python manage.py invite_doctor <token>         # trace one link
    python manage.py invite_doctor https://.../invite/<token>
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Cohort, Enrollment, Invitation, InvitationStatus


class Command(BaseCommand):
    help = 'Explain why an invite or registration token is not resolving.'

    def add_arguments(self, parser):
        parser.add_argument('token', nargs='?', default='', help='Token, or the whole link.')

    def handle(self, *args, **options):
        ok, warn, bad = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        self.stdout.write('\n== environment ==')
        db = settings.DATABASES['default']
        self.stdout.write(f"  database           {db.get('ENGINE', '').split('.')[-1]}: {db.get('NAME')}")
        self.stdout.write(f'  FRONTEND_BASE_URL  {getattr(settings, "FRONTEND_BASE_URL", "(unset)")}')
        self.stdout.write(f'  MAIL_BACKEND       {getattr(settings, "MAIL_BACKEND", "(unset)")}')

        base = getattr(settings, 'FRONTEND_BASE_URL', '') or ''
        if 'localhost' in base or '127.0.0.1' in base:
            self.stdout.write(warn(
                '  ^ links built here point at a developer machine. On a server that is wrong.'
            ))
        if getattr(settings, 'MAIL_BACKEND', '') != 'mailjet':
            self.stdout.write(warn('  ^ MAIL_BACKEND is not "mailjet" - nothing is actually emailed.'))

        self.stdout.write('\n== what this database holds ==')
        pending = Invitation.objects.filter(status=InvitationStatus.PENDING).count()
        self.stdout.write(f'  cohorts            {Cohort.objects.count()}')
        self.stdout.write(f'  invitations        {Invitation.objects.count()} (pending {pending})')
        self.stdout.write(f'  enrollments        {Enrollment.objects.count()}')
        self.stdout.write(f'  registration links {Cohort.objects.exclude(registration_token="").count()}')
        if Invitation.objects.count() == 0 and Cohort.objects.count() == 0:
            self.stdout.write(bad(
                '  ^ this database is empty. The API you are serving is not the one your '
                'instructor console writes to.'
            ))

        raw = (options.get('token') or '').strip()
        if not raw:
            self.stdout.write('\nPass a token (or the whole link) to trace one.\n')
            return

        token = raw.rstrip('/').split('/')[-1]
        self.stdout.write(f'\n== tracing {token!r} ==')

        invitation = Invitation.objects.filter(token=token).first()
        if invitation:
            self.stdout.write(ok('  found: an INVITATION'))
            self.stdout.write(f'    email      {invitation.email}')
            self.stdout.write(f'    cohort     {invitation.cohort.name if invitation.cohort else "(none)"}')
            self.stdout.write(f'    status     {invitation.status}')
            self.stdout.write(f'    sent_at    {invitation.sent_at or "never"}')
            if invitation.send_error:
                self.stdout.write(bad(f'    send_error {invitation.send_error}'))
            if invitation.status != InvitationStatus.PENDING:
                self.stdout.write(bad(
                    f'  -> rejected: status is {invitation.status}, not PENDING. Already used; '
                    'resend to issue a fresh link.'
                ))
            elif not invitation.cohort:
                self.stdout.write(bad('  -> rejected: not attached to a cohort.'))
            else:
                self.stdout.write(ok(
                    '  -> this token SHOULD resolve. If the page still says invalid, the '
                    'browser is reaching a different API than this database.'
                ))
            return

        cohort = Cohort.objects.filter(registration_token=token).first()
        if cohort:
            enrolled = Enrollment.objects.filter(cohort=cohort).count()
            capacity = cohort.enrollment_capacity or 0
            self.stdout.write(ok('  found: a COHORT REGISTRATION link'))
            self.stdout.write(f'    cohort     {cohort.name}')
            self.stdout.write(f'    seats      {enrolled}/{capacity or "unlimited"}')
            if capacity and enrolled >= capacity:
                self.stdout.write(bad('  -> the cohort is full; joining is refused.'))
            else:
                self.stdout.write(ok('  -> this token SHOULD resolve.'))
            return

        self.stdout.write(bad('  no invitation and no cohort in THIS database carries that token.'))
        self.stdout.write(
            '\n  Which means one of:\n'
            '    1. The link came from a different backend (a laptop, a staging box) than\n'
            '       the one this command just inspected.\n'
            '    2. The invitation was resent - resending rotates the token, so any earlier\n'
            '       email is dead. Open the most recent one.\n'
            '    3. The database was replaced since the link was made (a deploy that ships\n'
            '       or overwrites db.sqlite3 does this).\n'
        )
        recent = Invitation.objects.order_by('-created_at')[:5]
        if recent:
            self.stdout.write('  most recent invitations in this database:')
            for inv in recent:
                self.stdout.write(
                    f'    {inv.created_at:%Y-%m-%d %H:%M}  {inv.email:32s} {inv.status:9s} {inv.token}'
                )
