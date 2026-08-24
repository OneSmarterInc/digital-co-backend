from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import User
from .state import advance_gate, append_decision, default_run_state, validate_run_state


class RunStateTests(TestCase):
    def test_default_state_validates(self):
        state = default_run_state()
        self.assertTrue(validate_run_state(state))

    def test_append_decision_is_append_only(self):
        state = default_run_state()
        updated = append_decision(
            state,
            week=1,
            decision_key='choice',
            choice='balanced',
            trap_flags=[],
        )
        self.assertEqual(state['decision_history'], [])
        self.assertEqual(len(updated['decision_history']), 1)

    def test_gate_cannot_move_backward(self):
        state = advance_gate(default_run_state(), 'security_ot', to_state='detonated', week=10)
        with self.assertRaises(ValidationError):
            advance_gate(state, 'security_ot', to_state='closed', week=11)

    def test_v2_rejects_old_gate_name(self):
        state = default_run_state()
        state['gates']['ot_security'] = state['gates'].pop('security_ot')
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_v2_rejects_board_confidence_scalar(self):
        state = default_run_state()
        state['board_confidence'] = 3
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_known_flag_values_are_validated(self):
        state = default_run_state()
        state['flags']['board_verdict'] = 'maybe'
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_innovation_capability_catalog_matches_week5_values(self):
        state = default_run_state()
        state['flags']['innovation_capability'] = 'embedded'
        self.assertTrue(validate_run_state(state))

    def test_data_rights_week8_postures_are_valid(self):
        for posture in ('shared_value', 'asserted', 'contested_aggressive'):
            state = default_run_state()
            state['through_lines']['data_rights']['posture'] = posture
            self.assertTrue(validate_run_state(state))

    def test_keystone_coherence_weight_is_valid(self):
        state = default_run_state()
        state['through_lines']['coherence']['drift_events'].append({
            'week': 8,
            'kind': 'land_grab',
            'weight': 'keystone',
        })
        self.assertTrue(validate_run_state(state))

# Create your tests here.


class UsernameOrEmailLoginTests(TestCase):
    """Either identifier signs you in, and the ambiguous cases are decided
    rather than guessed."""

    def setUp(self):
        from core.models import UserRole
        self.password = 'a-long-enough-test-password'
        self.staff = User.objects.create_user(
            username='vikram-test', email='Vikram@Example.com',
            password=self.password, role=UserRole.ADMIN,
        )

    def _auth(self, identifier, password=None):
        from django.contrib.auth import authenticate
        return authenticate(username=identifier, password=password or self.password)

    def test_username_still_works(self):
        self.assertEqual(self._auth('vikram-test'), self.staff)

    def test_email_now_works(self):
        self.assertEqual(self._auth('Vikram@Example.com'), self.staff)

    def test_email_is_case_insensitive(self):
        self.assertEqual(self._auth('vikram@example.com'), self.staff)
        self.assertEqual(self._auth('VIKRAM@EXAMPLE.COM'), self.staff)

    def test_a_wrong_password_still_fails_on_either_identifier(self):
        self.assertIsNone(self._auth('vikram-test', 'wrong-password'))
        self.assertIsNone(self._auth('vikram@example.com', 'wrong-password'))

    def test_an_inactive_account_cannot_sign_in_by_email(self):
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        self.assertIsNone(self._auth('vikram@example.com'))
        self.assertIsNone(self._auth('vikram-test'))

    def test_a_username_beats_someone_elses_email(self):
        """If one person's email is another's username, the username owner keeps
        their login — otherwise adding this feature would silently move an
        existing account's sign-in to a different person."""
        from core.models import UserRole
        other = User.objects.create_user(
            username='shared@example.com', password=self.password, role=UserRole.STUDENT,
        )
        self.staff.email = 'shared@example.com'
        self.staff.save(update_fields=['email'])
        self.assertEqual(self._auth('shared@example.com'), other)

    def test_an_address_on_two_accounts_signs_in_neither(self):
        """Email is not unique in this schema. Picking one would be a guess
        about who is at the keyboard."""
        from core.models import UserRole
        User.objects.create_user(
            username='twin', email='Vikram@Example.com',
            password=self.password, role=UserRole.STUDENT,
        )
        self.assertIsNone(self._auth('vikram@example.com'))
        # Each can still sign in by their own username.
        self.assertEqual(self._auth('vikram-test'), self.staff)

    def test_a_student_whose_username_is_their_email_is_unaffected(self):
        from core.models import UserRole
        student = User.objects.create_user(
            username='test-9@mailinator.com', email='test-9@mailinator.com',
            password=self.password, role=UserRole.STUDENT,
        )
        self.assertEqual(self._auth('test-9@mailinator.com'), student)


class UsernameToEmailCommandTests(TestCase):
    """Renaming is not undoable from the command, so the guards matter more than
    the rename does."""

    def _run(self, **kwargs):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('username_to_email', stdout=out, **kwargs)
        return out.getvalue()

    def test_it_reports_without_changing_anything_by_default(self):
        from core.models import UserRole
        user = User.objects.create_user(
            username='shortname', email='person@example.com', password='pw', role=UserRole.ADMIN,
        )
        output = self._run()
        self.assertIn('shortname  ->  person@example.com', output)
        self.assertIn('Report only', output)
        user.refresh_from_db()
        self.assertEqual(user.username, 'shortname')

    def test_apply_renames(self):
        from core.models import UserRole
        user = User.objects.create_user(
            username='shortname', email='person@example.com', password='pw', role=UserRole.ADMIN,
        )
        self._run(apply=True)
        user.refresh_from_db()
        self.assertEqual(user.username, 'person@example.com')

    def test_the_password_survives_the_rename(self):
        from django.contrib.auth import authenticate
        from core.models import UserRole
        User.objects.create_user(
            username='shortname', email='person@example.com',
            password='a-long-enough-password', role=UserRole.ADMIN,
        )
        self._run(apply=True)
        self.assertIsNotNone(authenticate(
            username='person@example.com', password='a-long-enough-password'))

    def test_a_rename_that_would_collide_is_refused(self):
        """Usernames are unique. Renaming into an existing one would fail, and
        forcing it would lock the other account out entirely."""
        from core.models import UserRole
        incumbent = User.objects.create_user(
            username='taken@example.com', password='pw', role=UserRole.STUDENT,
        )
        mover = User.objects.create_user(
            username='mover', email='taken@example.com', password='pw', role=UserRole.ADMIN,
        )
        output = self._run(apply=True)
        self.assertIn('BLOCKED', output)
        mover.refresh_from_db()
        incumbent.refresh_from_db()
        self.assertEqual(mover.username, 'mover')
        self.assertEqual(incumbent.username, 'taken@example.com')

    def test_an_account_with_no_email_is_left_alone(self):
        from core.models import UserRole
        user = User.objects.create_user(username='nomail', password='pw', role=UserRole.STUDENT)
        self._run(apply=True)
        user.refresh_from_db()
        self.assertEqual(user.username, 'nomail')

    def test_only_limits_the_change(self):
        from core.models import UserRole
        a = User.objects.create_user(
            username='alpha', email='alpha@example.com', password='pw', role=UserRole.ADMIN)
        b = User.objects.create_user(
            username='beta', email='beta@example.com', password='pw', role=UserRole.ADMIN)
        self._run(apply=True, only='alpha')
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.username, 'alpha@example.com')
        self.assertEqual(b.username, 'beta')
