"""Explain why a sign-in is being refused.

Run this ON THE MACHINE THAT SERVES THE API. "No active account found with the
given credentials" is returned for every failure mode there is — wrong database,
absent user, wrong password, inactive account — so the message itself tells you
nothing. This separates them.

    python manage.py login_doctor                       # environment only
    python manage.py login_doctor vikram                # trace one identifier
    python manage.py login_doctor vikram --password     # prompt, then verify

The password is read from a prompt and never echoed, never logged, and never
taken as a command-line argument, where it would land in shell history.
"""
from getpass import getpass

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.management.base import BaseCommand

from core.models import User


class Command(BaseCommand):
    help = 'Explain why a username or email will not sign in.'

    def add_arguments(self, parser):
        parser.add_argument('identifier', nargs='?', default='', help='Username or email.')
        parser.add_argument(
            '--password', action='store_true',
            help='Prompt for the password and report whether it authenticates.',
        )

    def handle(self, *args, **options):
        ok, warn, bad = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        self.stdout.write('\n== environment ==')
        db = settings.DATABASES['default']
        self.stdout.write(f"  database   {db.get('ENGINE', '').split('.')[-1]}: {db.get('NAME')}")
        backends = getattr(settings, 'AUTHENTICATION_BACKENDS', [])
        self.stdout.write(f'  backends   {", ".join(backends) or "(Django default)"}')
        email_login = any('UsernameOrEmail' in b for b in backends)
        self.stdout.write(
            ok('  ^ email sign-in is enabled.') if email_login
            else warn('  ^ email sign-in is NOT enabled here — only the username works. '
                      'This build predates that change; redeploy.')
        )
        self.stdout.write(f'  users      {User.objects.count()} '
                          f'({User.objects.filter(is_active=True).count()} active)')
        if User.objects.count() == 0:
            self.stdout.write(bad('  ^ this database is empty. The API you are serving is not '
                                  'the one your seed command wrote to.'))

        identifier = options['identifier']
        if not identifier:
            self.stdout.write('\nPass a username or email to trace one account.\n')
            return

        self.stdout.write(f'\n== {identifier} ==')
        by_name = User.objects.filter(username=identifier).first()
        by_mail = list(User.objects.filter(email__iexact=identifier)[:3])

        if by_name:
            self.stdout.write(ok(f'  matches a USERNAME: {by_name.username}'))
        else:
            self.stdout.write(f'  no user has this as a username')
        if by_mail:
            names = ', '.join(u.username for u in by_mail)
            self.stdout.write(ok(f'  matches an EMAIL on: {names}'))
            if len(by_mail) > 1:
                self.stdout.write(bad('  ^ more than one account shares this address, so email '
                                      'sign-in is refused for it. Use the username.'))
            elif not email_login:
                self.stdout.write(warn('  ^ but email sign-in is not enabled on this build.'))
        else:
            self.stdout.write('  no user has this as an email')

        user = by_name or (by_mail[0] if len(by_mail) == 1 else None)
        if user is None:
            self.stdout.write(bad('\n  Nothing to sign in as. Either the account was never '
                                  'created here, or it was created in another database.'))
            return

        self.stdout.write(f'  active     {user.is_active}')
        self.stdout.write(f'  role       {user.role}  staff={user.is_staff} super={user.is_superuser}')
        self.stdout.write(f'  email      {user.email!r}')
        self.stdout.write(f'  password   {"set" if user.has_usable_password() else "UNUSABLE - never set"}')
        if not user.is_active:
            self.stdout.write(bad('  ^ inactive accounts are refused regardless of password.'))
        if not user.has_usable_password():
            self.stdout.write(bad('  ^ set one with: python manage.py changepassword '
                                  f'{user.username}'))

        if options['password']:
            supplied = getpass('\n  password (not echoed): ')
            result = authenticate(username=identifier, password=supplied)
            if result is not None:
                self.stdout.write(ok('  -> authenticates. The API will accept this sign-in.'))
            else:
                self.stdout.write(bad('  -> refused. The password does not match, or the '
                                      'identifier is not usable on this build.'))
                self.stdout.write('     Reset it with: python manage.py changepassword '
                                  f'{user.username}')
        self.stdout.write('')
