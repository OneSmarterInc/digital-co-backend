"""The invite flow, end to end: send -> read -> redeem.

Delivery runs through the recording backend; the Mailjet backend itself is
exercised only for its configuration guard, because asserting against a live
send would mail real people from the test suite.
"""
import secrets

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from api.instructor_api import InstructorInviteResendView, InstructorInviteView
from api.invite_api import InviteAcceptView, InviteDetailView
from core.models import (
    Cohort, Enrollment, Invitation, InvitationStatus, Team, Tier, User, UserRole,
)
from mailer import backends
from mailer.backends import LocmemBackend, Message, SendError
from mailer.invites import build_invite_message, send_invitation


class MailerTestCase(TestCase):
    def setUp(self):
        self.outbox = LocmemBackend()
        backends.set_backend(self.outbox)
        self.addCleanup(backends.set_backend, None)

        self.instructor = User.objects.create_user(
            username='prof@example.com', password='pw', role=UserRole.INSTRUCTOR,
            first_name='Ada', last_name='Byron',
        )
        self.cohort = Cohort.objects.create(name='SIM-INVITE', tier=Tier.GRADUATE)
        self.cohort.instructors.add(self.instructor)
        self.team = Team.objects.create(cohort=self.cohort, name='Team 1')

    def _invitation(self, email='student@example.com', team=None):
        return Invitation.objects.create(
            cohort=self.cohort, email=email, token=secrets.token_urlsafe(24),
            invited_by=self.instructor, team=team,
        )


@override_settings(FRONTEND_BASE_URL='https://sim.example.edu')
class InviteMessageTests(MailerTestCase):
    def test_the_email_carries_a_working_link_and_no_scenario_content(self):
        invitation = self._invitation()
        message = build_invite_message(invitation)

        url = f'https://sim.example.edu/invite/{invitation.token}'
        self.assertIn(url, message.text)
        self.assertIn(url, message.html)
        self.assertIn('SIM-INVITE', message.subject)
        self.assertEqual(message.to_email, 'student@example.com')
        self.assertIn('Ada Byron', message.text)

        # The first thing a student receives must not pre-empt the simulation.
        body = (message.text + message.html).lower()
        for leak in ('calloway', 'reinhardt', 's/4hana', 'trap', 'advisor time', 'coherence'):
            self.assertNotIn(leak, body, f'invite email leaked {leak!r}')

    def test_sending_records_delivery_on_the_invitation(self):
        invitation = self._invitation()
        sent, _ = send_invitation(invitation)
        invitation.refresh_from_db()

        self.assertTrue(sent)
        self.assertIsNotNone(invitation.sent_at)
        self.assertEqual(invitation.send_error, '')
        self.assertEqual(len(self.outbox.outbox), 1)

    def test_a_failed_send_records_the_error_and_keeps_the_invitation(self):
        backends.set_backend(LocmemBackend(fail_with='mailbox full'))
        invitation = self._invitation()

        sent, detail = send_invitation(invitation)
        invitation.refresh_from_db()

        self.assertFalse(sent)
        self.assertIn('mailbox full', detail)
        self.assertIn('mailbox full', invitation.send_error)
        self.assertIsNone(invitation.sent_at)
        # The record survives, so the instructor can resend.
        self.assertTrue(Invitation.objects.filter(pk=invitation.pk).exists())


class InviteEndpointTests(MailerTestCase):
    def _post_invite(self, email):
        request = APIRequestFactory().post('/x', {'email': email}, format='json')
        force_authenticate(request, user=self.instructor)
        return InstructorInviteView.as_view()(request, cohort_id=self.cohort.id)

    def test_inviting_a_student_sends_the_email(self):
        resp = self._post_invite('new@example.com')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['sent'])
        self.assertEqual(len(self.outbox.outbox), 1)
        self.assertEqual(self.outbox.outbox[0].to_email, 'new@example.com')

    def _resend(self, invitation, **body):
        request = APIRequestFactory().post('/x', body, format='json')
        force_authenticate(request, user=self.instructor)
        return InstructorInviteResendView.as_view()(
            request, cohort_id=self.cohort.id, invitation_id=invitation.id,
        )

    def test_resending_keeps_the_token_so_earlier_emails_still_work(self):
        """The failure this guards: an instructor chasing a student resends
        twice, and every copy already in that inbox stops working."""
        self._post_invite('new@example.com')
        invitation = Invitation.objects.get(email='new@example.com')
        first_token = invitation.token

        self.assertEqual(self._resend(invitation).status_code, 200)
        self.assertEqual(self._resend(invitation).status_code, 200)
        invitation.refresh_from_db()

        self.assertEqual(invitation.token, first_token)
        self.assertEqual(len(self.outbox.outbox), 3)
        # Every link ever emailed for this invitation is the same one.
        self.assertEqual(
            {m.text.split('/invite/')[1].split()[0] for m in self.outbox.outbox},
            {first_token},
        )

    def test_reissue_retires_the_old_links_when_asked(self):
        self._post_invite('new@example.com')
        invitation = Invitation.objects.get(email='new@example.com')
        old_token = invitation.token

        self.assertEqual(self._resend(invitation, reissue=True).status_code, 200)
        invitation.refresh_from_db()
        self.assertNotEqual(invitation.token, old_token)


class InviteRedemptionTests(MailerTestCase):
    def _detail(self, token):
        return InviteDetailView.as_view()(APIRequestFactory().get('/x'), token=token)

    def _accept(self, token, **body):
        payload = {'first_name': 'Grace', 'last_name': 'Hopper',
                   'password': 'correct-horse', 'password_confirm': 'correct-horse'}
        payload.update(body)
        return InviteAcceptView.as_view()(
            APIRequestFactory().post('/x', payload, format='json'), token=token,
        )

    def test_detail_describes_what_is_being_accepted(self):
        invitation = self._invitation(team=self.team)
        resp = self._detail(invitation.token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['cohort'], 'SIM-INVITE')
        self.assertEqual(resp.data['firm'], 'Team 1')
        self.assertFalse(resp.data['has_account'])

    def test_accepting_creates_the_account_enrollment_and_firm_seat(self):
        invitation = self._invitation(team=self.team)
        resp = self._accept(invitation.token)
        self.assertEqual(resp.status_code, 201)

        user = User.objects.get(username='student@example.com')
        self.assertEqual(user.first_name, 'Grace')
        self.assertEqual(user.role, UserRole.STUDENT)
        self.assertTrue(Enrollment.objects.filter(cohort=self.cohort, student=user).exists())
        self.assertIn(user, self.team.members.all())

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertEqual(invitation.accepted_by, user)

    def test_a_token_only_works_once(self):
        invitation = self._invitation(team=self.team)
        self.assertEqual(self._accept(invitation.token).status_code, 201)
        second = self._accept(invitation.token)
        self.assertEqual(second.status_code, 404)
        self.assertEqual(User.objects.filter(username='student@example.com').count(), 1)

    def test_unknown_and_used_tokens_are_indistinguishable(self):
        invitation = self._invitation()
        self._accept(invitation.token)
        used = self._detail(invitation.token)
        unknown = self._detail('not-a-real-token')
        self.assertEqual(used.status_code, unknown.status_code, 404)
        self.assertEqual(used.data['detail'], unknown.data['detail'])

    def test_a_short_password_is_rejected_per_field(self):
        invitation = self._invitation()
        resp = self._accept(invitation.token, password='abc', password_confirm='abc')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('password', resp.data['errors'])
        self.assertFalse(User.objects.filter(username='student@example.com').exists())

    def test_mismatched_passwords_are_rejected(self):
        invitation = self._invitation()
        resp = self._accept(invitation.token, password_confirm='something-else')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('password_confirm', resp.data['errors'])

    def test_without_a_preassigned_firm_the_student_stays_unallocated(self):
        """Firm allocation is the instructor's call. Accepting an invite must
        not quietly place a student — they wait, with only the tour to look at,
        until an instructor allocates them."""
        Team.objects.create(cohort=self.cohort, name='Team 2')
        invitation = self._invitation(team=None)
        self._accept(invitation.token)

        user = User.objects.get(username='student@example.com')
        enrollment = Enrollment.objects.get(cohort=self.cohort, student=user)
        self.assertIsNone(enrollment.team)
        for team in Team.objects.filter(cohort=self.cohort):
            self.assertNotIn(user, team.members.all())

    def test_a_preassigned_firm_on_the_invitation_is_honoured(self):
        invitation = self._invitation(team=self.team)
        self._accept(invitation.token)

        user = User.objects.get(username='student@example.com')
        self.assertEqual(Enrollment.objects.get(cohort=self.cohort, student=user).team, self.team)
        self.assertIn(user, self.team.members.all())


class MailjetConfigTests(TestCase):
    @override_settings(MAILJET_API_KEY='', MAILJET_API_SECRET='', MAIL_FROM_ADDRESS='')
    def test_an_unconfigured_mailjet_backend_refuses_to_pretend(self):
        with self.assertRaises(SendError) as caught:
            backends.MailjetBackend()
        self.assertIn('not configured', str(caught.exception))

    def test_the_default_backend_does_not_send(self):
        backends.set_backend(None)
        self.addCleanup(backends.set_backend, None)
        with override_settings(MAIL_BACKEND='console'):
            self.assertIsInstance(backends.get_backend(), backends.ConsoleBackend)


class SelfRegistrationTests(MailerTestCase):
    """The cohort-wide shared link. The instructor console has generated
    /register/<token> since before anything served it — every shared link was a
    dead page until these endpoints existed.
    """

    def setUp(self):
        super().setUp()
        self.cohort.registration_token = 'shared-token'
        self.cohort.enrollment_capacity = 2
        self.cohort.save(update_fields=['registration_token', 'enrollment_capacity'])

    def _detail(self, token='shared-token'):
        from api.invite_api import RegistrationDetailView
        return RegistrationDetailView.as_view()(APIRequestFactory().get('/x'), token=token)

    def _join(self, token='shared-token', **body):
        from api.invite_api import RegistrationAcceptView
        payload = {'email': 'joiner@example.com', 'first_name': 'Alan',
                   'password': 'correct-horse', 'password_confirm': 'correct-horse'}
        payload.update(body)
        return RegistrationAcceptView.as_view()(
            APIRequestFactory().post('/x', payload, format='json'), token=token,
        )

    def test_detail_reports_the_cohort_and_seats(self):
        resp = self._detail()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['cohort'], 'SIM-INVITE')
        self.assertEqual(resp.data['seats_left'], 2)
        self.assertFalse(resp.data['full'])

    def test_an_unknown_token_is_rejected(self):
        self.assertEqual(self._detail('nope').status_code, 404)
        self.assertEqual(self._join('nope').status_code, 404)

    def test_joining_creates_the_account_and_leaves_the_student_unallocated(self):
        resp = self._join()
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username='joiner@example.com')
        self.assertEqual(user.first_name, 'Alan')
        enrollment = Enrollment.objects.get(cohort=self.cohort, student=user)
        self.assertIsNone(enrollment.team)
        self.assertIsNone(resp.data['firm'])
        self.assertNotIn(user, self.team.members.all())

    def test_the_link_is_reusable_unlike_an_invitation(self):
        self.assertEqual(self._join(email='one@example.com').status_code, 201)
        self.assertEqual(self._join(email='two@example.com').status_code, 201)
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort).count(), 2)

    def test_capacity_is_enforced(self):
        self._join(email='one@example.com')
        self._join(email='two@example.com')
        full = self._join(email='three@example.com')
        self.assertEqual(full.status_code, 409)
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort).count(), 2)

    def test_joining_twice_is_refused_rather_than_duplicated(self):
        self._join()
        again = self._join()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort).count(), 1)

    def test_registering_spends_a_pending_invitation_for_the_same_address(self):
        invitation = self._invitation(email='joiner@example.com')
        self._join()
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)

    def test_a_bad_email_is_rejected_per_field(self):
        resp = self._join(email='not-an-email')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('email', resp.data['errors'])
