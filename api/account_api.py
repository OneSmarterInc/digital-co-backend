"""Choosing a password from an emailed link.

Public by design: the link is the credential and the person following it either
has no password yet (a new instructor) or has forgotten theirs. The token comes
from Django's password-reset generator, so it is derived from the current
password hash and last_login — setting a password invalidates the link, and so
does signing in.
"""
import logging

from django.contrib.auth.password_validation import ValidationError, validate_password
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User
from mailer.accounts import resolve_set_password, send_password_reset

MIN_PASSWORD_LENGTH = 8


logger = logging.getLogger(__name__)


def _gone():
    return Response(
        {'detail': 'This link is no longer valid. It may have been used already, or expired.'},
        status=404,
    )


class SetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, uidb64, token):
        """Who is this link for — so the page can greet them before they commit."""
        user = resolve_set_password(uidb64, token)
        if not user:
            return _gone()
        return Response({
            'email': user.email or user.username,
            'name': (user.get_full_name() or '').strip() or user.username,
            'role': user.role,
            # A first-time set reads differently from a reset.
            'has_password': user.has_usable_password(),
        })

    def post(self, request, uidb64, token):
        user = resolve_set_password(uidb64, token)
        if not user:
            return _gone()

        password = request.data.get('password') or ''
        confirm = request.data.get('password_confirm') or ''
        errors = {}
        if len(password) < MIN_PASSWORD_LENGTH:
            errors['password'] = f'Use at least {MIN_PASSWORD_LENGTH} characters.'
        elif confirm and password != confirm:
            errors['password_confirm'] = 'The two passwords do not match.'
        else:
            try:
                validate_password(password, user)
            except ValidationError as exc:
                errors['password'] = ' '.join(exc.messages)
        if errors:
            return Response({'detail': 'Some fields need attention.', 'errors': errors}, status=400)

        user.set_password(password)
        user.save(update_fields=['password'])
        # The token was derived from the old hash, so it is now spent.
        return Response({'ok': True, 'email': user.email or user.username})


class PasswordResetRequestView(APIView):
    """Ask for a reset link. Public, because the person cannot sign in.

    Always answers the same way whether or not the account exists. The response
    is the only signal available to an unauthenticated caller, so varying it
    would turn this into a way to test which addresses are enrolled — and a
    course roster is exactly the kind of list worth not leaking.

    Accepts a username or an email, matching the sign-in field, so someone who
    signs in with `vikram` does not have to remember which one this wants.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    # Said whether or not anything was found or sent.
    SENT = (
        'If that account exists, a reset link is on its way. '
        'Check your inbox, and your spam folder.'
    )

    def post(self, request):
        identifier = str(request.data.get('identifier') or '').strip()
        if not identifier:
            return Response({'detail': 'Enter your email address or username.'}, status=400)

        user = (
            User.objects.filter(username__iexact=identifier).first()
            or User.objects.filter(email__iexact=identifier).first()
        )

        # Inactive accounts are treated as absent: a blocked or disabled account
        # should not be recoverable by the person holding the old address.
        if user and user.is_active:
            sent, _url, error = send_password_reset(user)
            if not sent:
                # Logged for the operator, never returned: "this account has no
                # email on file" tells a stranger the account exists.
                logger.warning(
                    'password reset for %s could not be sent: %s', user.username, error,
                )

        return Response({'detail': self.SENT})
