"""The student invitation email.

Written as a person writing to a student, not as a system notification: the
first thing a student ever receives from this course should read like the course.
It carries what they are being invited to, one link, and nothing else — no
scenario content, no advisor names, no mention of what Week 1 contains.
"""
from django.conf import settings

from .backends import Message, SendError, get_backend


def invite_url(token: str) -> str:
    base = (getattr(settings, 'FRONTEND_BASE_URL', '') or '').rstrip('/')
    return f'{base}/invite/{token}'


def _tier_word(cohort) -> str:
    return 'graduate' if getattr(cohort, 'tier', '') == 'GRADUATE' else 'undergraduate'


def build_invite_message(invitation) -> Message:
    cohort = invitation.cohort
    cohort_name = cohort.name if cohort else 'DigitalCo'
    url = invite_url(invitation.token)
    inviter = invitation.invited_by
    inviter_name = ''
    if inviter:
        inviter_name = (inviter.get_full_name() or '').strip() or inviter.username

    subject = f'Your seat in {cohort_name}'

    text = f"""You have been given a seat in {cohort_name}, a fourteen-week strategy simulation
where your team runs the IT organisation of a manufacturer called DigitalCo.

Set up your account here:

{url}

You will pick a password and see your firm. The simulation opens at Round 1;
everything you need is inside, and there is a walkthrough under the "?" in the
top right of every screen.

This link is yours alone — it is tied to {invitation.email}, and it stops working
once you have used it.
"""
    if inviter_name:
        text += f'\nInvited by {inviter_name}.\n'

    html = f"""<div style="background:#16191D;padding:32px 0;font-family:'IBM Plex Sans',Helvetica,Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;background:#1E2228;border:1px solid #2C323A;border-radius:4px;overflow:hidden">
    <div style="height:3px;background:#E8A13C"></div>
    <div style="padding:28px 30px">
      <p style="margin:0 0 18px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#5C6672">
        FLEXEE &middot; <span style="color:#E8A13C">DigitalCo</span>
      </p>
      <h1 style="margin:0 0 14px;font-size:26px;line-height:1.15;color:#ECEFF2;font-weight:700">
        Your seat in {cohort_name}
      </h1>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#8A94A0">
        A fourteen-week {_tier_word(cohort)} strategy simulation. Your team runs the IT
        organisation of a manufacturer called DigitalCo &mdash; one chair, one voice,
        fourteen decisions.
      </p>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#8A94A0">
        Set up your account and you will see your firm.
      </p>
      <a href="{url}"
         style="display:inline-block;background:#E8A13C;color:#16191D;text-decoration:none;
                padding:13px 28px;border-radius:2px;font-weight:700;font-size:15px;
                letter-spacing:.04em;text-transform:uppercase">
        Take your seat
      </a>
      <p style="margin:22px 0 0;font-size:13px;line-height:1.6;color:#5C6672">
        Or paste this into your browser:<br>
        <span style="color:#8A94A0;word-break:break-all">{url}</span>
      </p>
      <p style="margin:20px 0 0;padding-top:16px;border-top:1px solid #2C323A;font-size:12px;line-height:1.6;color:#5C6672">
        This link is tied to {invitation.email} and stops working once you have used it.
        {f'Invited by {inviter_name}.' if inviter_name else ''}
      </p>
    </div>
  </div>
</div>"""

    return Message(to_email=invitation.email, subject=subject, text=text, html=html)


def send_invitation(invitation) -> tuple[bool, str]:
    """Send one invite and record the outcome on the invitation.

    Returns (sent, detail). Never raises: a delivery failure must not lose the
    invitation record or fail the instructor's request — they can resend.
    """
    from django.utils import timezone

    try:
        receipt = get_backend().send(build_invite_message(invitation))
    except SendError as exc:
        invitation.send_error = str(exc)[:500]
        invitation.save(update_fields=['send_error'])
        return False, str(exc)
    except Exception as exc:  # a backend blowing up is still not the caller's problem
        invitation.send_error = f'Unexpected mail error: {exc}'[:500]
        invitation.save(update_fields=['send_error'])
        return False, str(exc)

    invitation.sent_at = timezone.now()
    invitation.send_error = ''
    invitation.save(update_fields=['sent_at', 'send_error'])
    return True, receipt
