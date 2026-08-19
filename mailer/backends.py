"""Email delivery.

Three backends, chosen by MAIL_BACKEND:

  mailjet — the real thing, over Mailjet's Send API v3.1
  console — prints the message; the default, so a fresh checkout never sends
  locmem  — records in memory; what the tests assert against

Delivery never raises into a request. An invite that fails to send is still a
created invitation with a recorded error, because losing the invite record
because the mail server hiccuped is worse than a delayed email.
"""
import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings

MAILJET_ENDPOINT = 'https://api.mailjet.com/v3.1/send'
TIMEOUT_SECONDS = 15


@dataclass
class Message:
    to_email: str
    subject: str
    text: str
    html: str = ''
    to_name: str = ''


class SendError(Exception):
    """Delivery failed. Carries something an instructor can act on."""


class ConsoleBackend:
    """Prints instead of sending. The default — a checkout with no credentials
    must not silently appear to be emailing students."""

    def send(self, message: Message) -> str:
        print(f'\n--- email to {message.to_email} ---\n{message.subject}\n\n{message.text}\n---\n')
        return 'console'


@dataclass
class LocmemBackend:
    """Records messages for tests. `outbox` is the assertion surface."""

    outbox: list = field(default_factory=list)
    fail_with: str = ''

    def send(self, message: Message) -> str:
        if self.fail_with:
            raise SendError(self.fail_with)
        self.outbox.append(message)
        return f'locmem-{len(self.outbox)}'


class MailjetBackend:
    """Mailjet Send API v3.1 over urllib — no extra dependency for one POST."""

    def __init__(self, api_key=None, api_secret=None, from_email=None, from_name=None):
        self.api_key = api_key or getattr(settings, 'MAILJET_API_KEY', '')
        self.api_secret = api_secret or getattr(settings, 'MAILJET_API_SECRET', '')
        self.from_email = from_email or getattr(settings, 'MAIL_FROM_ADDRESS', '')
        self.from_name = from_name or getattr(settings, 'MAIL_FROM_NAME', '') or 'FLEXEE'
        if not (self.api_key and self.api_secret and self.from_email):
            raise SendError(
                'Mailjet is not configured — set MAILJET_API_KEY, MAILJET_API_SECRET '
                'and MAIL_FROM_ADDRESS.'
            )

    def send(self, message: Message) -> str:
        payload = {
            'Messages': [{
                'From': {'Email': self.from_email, 'Name': self.from_name},
                'To': [{'Email': message.to_email, 'Name': message.to_name or message.to_email}],
                'Subject': message.subject,
                'TextPart': message.text,
                **({'HTMLPart': message.html} if message.html else {}),
            }],
        }
        token = base64.b64encode(f'{self.api_key}:{self.api_secret}'.encode()).decode()
        request = urllib.request.Request(
            MAILJET_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': f'Basic {token}'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode() or '{}')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors='replace')[:400]
            raise SendError(f'Mailjet rejected the message ({exc.code}): {detail}') from exc
        except urllib.error.URLError as exc:
            raise SendError(f"Couldn't reach Mailjet: {exc.reason}") from exc

        # v3.1 returns per-recipient status; a 200 can still carry a failure.
        results = body.get('Messages') or []
        first = results[0] if results else {}
        if first.get('Status') != 'success':
            errors = first.get('Errors') or []
            reason = errors[0].get('ErrorMessage') if errors else 'unknown reason'
            raise SendError(f'Mailjet did not accept the message: {reason}')
        sent = (first.get('To') or [{}])[0]
        return sent.get('MessageUUID') or 'sent'


_BACKENDS = {'mailjet': MailjetBackend, 'console': ConsoleBackend, 'locmem': LocmemBackend}
_override = None


def set_backend(backend):
    """Swap the backend for the process — used by tests."""
    global _override
    _override = backend


def get_backend():
    if _override is not None:
        return _override
    name = getattr(settings, 'MAIL_BACKEND', 'console')
    return _BACKENDS.get(name, ConsoleBackend)()
