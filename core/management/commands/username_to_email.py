"""Make each account's username its email address.

Students already sign in this way — the invite flow creates them with the email
as the username. Staff accounts were created with short names, so the address
they are told to use is not the one that signs them in.

Renaming is not undoable from here, so this reports by default and changes
nothing until you pass --apply.

    python manage.py username_to_email                  # report only
    python manage.py username_to_email --apply
    python manage.py username_to_email --apply --only vikram,john

Skipped, always:
  * accounts with no email — there is nothing to rename them to
  * accounts whose username already is their email
  * any rename that would collide with an existing username, since usernames
    are unique and the loser of that collision could no longer sign in at all
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = "Set each user's username to their email address."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Actually rename. Without this, nothing is written.')
        parser.add_argument('--only', default='',
                            help='Comma-separated usernames to limit the change to.')

    def handle(self, *args, **options):
        ok, warn, bad = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        queryset = User.objects.all().order_by('username')
        only = [n.strip() for n in options['only'].split(',') if n.strip()]
        if only:
            queryset = queryset.filter(username__in=only)
            missing = set(only) - set(queryset.values_list('username', flat=True))
            for name in sorted(missing):
                self.stdout.write(bad(f'  no such user: {name}'))

        planned, skipped, blocked = [], [], []
        for user in queryset:
            email = (user.email or '').strip()
            if not email:
                skipped.append((user.username, 'no email'))
                continue
            if user.username.lower() == email.lower():
                skipped.append((user.username, 'already signs in with this address'))
                continue
            if User.objects.filter(username__iexact=email).exclude(pk=user.pk).exists():
                blocked.append((user.username, email))
                continue
            planned.append((user, email))

        self.stdout.write('\n== plan ==')
        for user, email in planned:
            self.stdout.write(f'  {user.username}  ->  {email}')
        if not planned:
            self.stdout.write('  nothing to rename')
        for name, why in skipped:
            self.stdout.write(f'  {name}: skipped, {why}')
        for name, email in blocked:
            self.stdout.write(bad(f'  {name}: BLOCKED, {email} is already another '
                                  f'account\'s username'))

        if not options['apply']:
            self.stdout.write(warn('\nReport only. Re-run with --apply to make these changes.\n'))
            return

        with transaction.atomic():
            for user, email in planned:
                user.username = email
                user.save(update_fields=['username'])

        self.stdout.write(ok(f'\nRenamed {len(planned)} account(s).'))
        if planned:
            # Several screens fall back to the username when no name is set, so
            # a renamed account with an empty first name now reads as an email
            # address wherever a person's name belongs.
            nameless = [e for u, e in planned if not (u.first_name or '').strip()]
            if nameless:
                self.stdout.write(warn(
                    '\nThese accounts have no first name, so screens that fall back to the '
                    'username will now show an email address where a name belongs:'))
                for email in nameless:
                    self.stdout.write(f'  {email}')
                self.stdout.write('Set names in the admin, or with User.objects.filter(...)'
                                  '.update(first_name=...), to fix the display.')
        self.stdout.write('')
