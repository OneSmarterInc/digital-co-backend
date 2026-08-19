"""Set-password links, and the emails that carry them.

Uses Django's own password-reset token machinery rather than a bespoke token
table: the token is derived from the user's current password hash and
last_login, so it invalidates itself the moment the password is set or the
person signs in, and it expires on PASSWORD_RESET_TIMEOUT without anything
needing to be swept up.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from core.models import User

from .backends import Message, SendError, get_backend


def set_password_url(user) -> str:
    base = (getattr(settings, 'FRONTEND_BASE_URL', '') or '').rstrip('/')
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f'{base}/set-password/{uid}/{token}'


def resolve_set_password(uidb64: str, token: str):
    """The user this link is for, or None if it is unknown, spent or expired."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None


def build_faculty_invite(user, url: str, invited_by=None) -> Message:
    name = (user.get_full_name() or '').strip() or user.username
    inviter = ''
    if invited_by:
        inviter = (invited_by.get_full_name() or '').strip() or invited_by.username

    subject = 'Your FLEXEE · DigitalCo instructor account'
    text = f"""{name},

An instructor account has been created for you on FLEXEE · DigitalCo, the
platform that runs the DigitalCo strategy simulation.

Choose your password here:

{url}

You will sign in with {user.email or user.username}. From the instructor console
you can invite students, place them into firms, run the weekly rounds and grade
what they commit.

This link is single use and expires; if it has already lapsed, ask for another.
"""
    if inviter:
        text += f'\nAdded by {inviter}.\n'

    html = f"""<div style="background:#16191D;padding:32px 0;font-family:'IBM Plex Sans',Helvetica,Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;background:#1E2228;border:1px solid #2C323A;border-radius:4px;overflow:hidden">
    <div style="height:3px;background:#E8A13C"></div>
    <div style="padding:28px 30px">
      <p style="margin:0 0 18px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#5C6672">
        FLEXEE &middot; <span style="color:#E8A13C">DigitalCo</span>
      </p>
      <h1 style="margin:0 0 14px;font-size:25px;line-height:1.15;color:#ECEFF2;font-weight:700">
        Your instructor account
      </h1>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#8A94A0">
        {name}, an instructor account has been created for you. Choose a password
        and you can invite students, place them into firms, run the rounds and grade
        what they commit.
      </p>
      <a href="{url}"
         style="display:inline-block;background:#E8A13C;color:#16191D;text-decoration:none;
                padding:13px 28px;border-radius:2px;font-weight:700;font-size:15px;
                letter-spacing:.04em;text-transform:uppercase">
        Choose your password
      </a>
      <p style="margin:22px 0 0;font-size:13px;line-height:1.6;color:#5C6672">
        Or paste this into your browser:<br>
        <span style="color:#8A94A0;word-break:break-all">{url}</span>
      </p>
      <p style="margin:20px 0 0;padding-top:16px;border-top:1px solid #2C323A;font-size:12px;line-height:1.6;color:#5C6672">
        You sign in with {user.email or user.username}. This link is single use and expires.
        {f'Added by {inviter}.' if inviter else ''}
      </p>
    </div>
  </div>
</div>"""
    return Message(to_email=user.email or user.username, subject=subject, text=text, html=html, to_name=name)


def send_faculty_invite(user, invited_by=None) -> tuple[bool, str, str]:
    """Email a new instructor their set-password link.

    Returns (sent, url, error). The URL comes back either way: if the mail did
    not go, an admin needs to hand the link over directly rather than being left
    with an account nobody can sign in to.
    """
    url = set_password_url(user)
    try:
        get_backend().send(build_faculty_invite(user, url, invited_by))
    except Exception as exc:  # never fail the create over delivery
        return False, url, str(exc)
    return True, url, ''
