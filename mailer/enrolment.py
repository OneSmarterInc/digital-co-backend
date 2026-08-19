"""The email a student gets once they have accepted a place.

Sent at the moment they join, which is usually before an instructor has put them
in a firm. That gap is the point of this message: without it a student accepts
an invite, lands on a console that will not let them do anything, and reasonably
concludes something is broken.

Carries no scenario content — same discipline as the invite itself.
"""
from django.conf import settings

from .backends import Message, SendError, get_backend


def _console_url(cohort_id) -> str:
    base = (getattr(settings, 'FRONTEND_BASE_URL', '') or '').rstrip('/')
    return f'{base}/student/{cohort_id}'


def build_enrolment_message(user, cohort, team=None) -> Message:
    name = (user.first_name or '').strip() or (user.get_full_name() or '').strip() or user.username
    url = _console_url(cohort.id)
    placed = team is not None

    if placed:
        middle_text = (
            f'You are in {team.name}. That is the firm you will run for the whole term —\n'
            'one chair, one voice, fourteen decisions.'
        )
        middle_html = (
            f'You are in <b style="color:#ECEFF2">{team.name}</b>. That is the firm you will run '
            'for the whole term &mdash; one chair, one voice, fourteen decisions.'
        )
        action = 'Open the simulation'
    else:
        middle_text = (
            'You have not been placed in a firm yet. Your instructor assigns firms once\n'
            'the roster settles, so there is nothing to decide just yet.\n\n'
            'What you can do now is watch the opening tour. It walks through how a week\n'
            'works — read the briefing, consult the advisors, converge as a team, commit\n'
            'the decision — and you only get one first read of it. The moment your\n'
            'instructor places you in a firm, the simulation opens.'
        )
        middle_html = (
            'You have <b style="color:#ECEFF2">not been placed in a firm yet</b>. Your instructor '
            'assigns firms once the roster settles, so there is nothing to decide just yet.'
            '</p><p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#8A94A0">'
            'What you can do now is watch the opening tour. It walks through how a week works '
            '&mdash; read the briefing, consult the advisors, converge as a team, commit the '
            'decision &mdash; and you only get one first read of it. The moment your instructor '
            'places you in a firm, the simulation opens.'
        )
        action = 'Watch the tour'

    subject = f'You are enrolled in {cohort.name}'
    text = f"""{name},

You are enrolled in {cohort.name}.

{middle_text}

{action}:

{url}
"""
    html = f"""<div style="background:#16191D;padding:32px 0;font-family:'IBM Plex Sans',Helvetica,Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;background:#1E2228;border:1px solid #2C323A;border-radius:4px;overflow:hidden">
    <div style="height:3px;background:#E8A13C"></div>
    <div style="padding:28px 30px">
      <p style="margin:0 0 18px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#5C6672">
        FLEXEE &middot; <span style="color:#E8A13C">DigitalCo</span>
      </p>
      <h1 style="margin:0 0 14px;font-size:25px;line-height:1.15;color:#ECEFF2;font-weight:700">
        You&rsquo;re enrolled in {cohort.name}
      </h1>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#8A94A0">{middle_html}</p>
      <a href="{url}"
         style="display:inline-block;background:#E8A13C;color:#16191D;text-decoration:none;
                padding:13px 28px;border-radius:2px;font-weight:700;font-size:15px;
                letter-spacing:.04em;text-transform:uppercase">
        {action}
      </a>
      <p style="margin:22px 0 0;font-size:13px;line-height:1.6;color:#5C6672">
        Or paste this into your browser:<br>
        <span style="color:#8A94A0;word-break:break-all">{url}</span>
      </p>
    </div>
  </div>
</div>"""
    return Message(to_email=user.email or user.username, subject=subject, text=text, html=html, to_name=name)


def send_enrolment_confirmation(user, cohort, team=None) -> tuple[bool, str]:
    """Never raises: a student who is enrolled stays enrolled even if the
    confirmation cannot be delivered."""
    try:
        get_backend().send(build_enrolment_message(user, cohort, team))
    except (SendError, Exception) as exc:  # noqa: B014
        return False, str(exc)
    return True, 'sent'
