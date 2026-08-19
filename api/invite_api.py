"""Accepting an invitation.

The invite half of the loop was never built: tokens were generated, and nothing
could redeem them. These two endpoints are the student's side of it — read the
invitation, then turn it into an account, an enrollment, and a firm seat.

Both are deliberately unauthenticated: the token IS the credential, and the
person using it does not have an account yet. The token is single-use, and a
redeemed or unknown token is indistinguishable in the response so the endpoint
can't be used to probe which emails were invited.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Cohort, Enrollment, Invitation, InvitationStatus, User, UserRole,
)

MIN_PASSWORD_LENGTH = 8


def _gone():
    """One response for unknown, expired and already-used tokens alike, so the
    endpoint reveals nothing about who was invited."""
    return Response(
        {'detail': 'This invitation link is not valid. It may have already been used.'},
        status=404,
    )


def _open_invitation(token):
    invitation = (
        Invitation.objects
        .select_related('cohort', 'team')
        .filter(token=token, status=InvitationStatus.PENDING)
        .first()
    )
    return invitation


class InviteDetailView(APIView):
    """What is this invitation for? Read-only, so the page can show the student
    what they are accepting before they commit to anything."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        invitation = _open_invitation(token)
        if not invitation or not invitation.cohort:
            return _gone()
        cohort = invitation.cohort
        return Response({
            'email': invitation.email,
            'cohort': cohort.name,
            'tier': cohort.tier,
            'firm': invitation.team.name if invitation.team else None,
            'start_date': cohort.start_date.isoformat() if cohort.start_date else None,
            'total_rounds': 14,
            # True when the address already has an account — the page then asks
            # them to sign in rather than choose a password.
            'has_account': User.objects.filter(username__iexact=invitation.email).exists(),
        })


class InviteAcceptView(APIView):
    """Redeem the token: create (or reuse) the account, enroll, seat the firm."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        invitation = _open_invitation(token)
        if not invitation or not invitation.cohort:
            return _gone()

        errors = {}
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()
        password = request.data.get('password') or ''
        confirm = request.data.get('password_confirm') or ''

        existing = User.objects.filter(username__iexact=invitation.email).first()
        if not first_name:
            errors['first_name'] = 'Tell us your first name.'
        if not existing:
            if len(password) < MIN_PASSWORD_LENGTH:
                errors['password'] = f'Use at least {MIN_PASSWORD_LENGTH} characters.'
            elif confirm and password != confirm:
                errors['password_confirm'] = 'The two passwords do not match.'
        if errors:
            return Response({'detail': 'Some fields need attention.', 'errors': errors}, status=400)

        cohort = invitation.cohort
        with transaction.atomic():
            # Re-read under the lock: two students clicking the same link at once
            # must not both redeem it.
            locked = (
                Invitation.objects.select_for_update()
                .filter(pk=invitation.pk, status=InvitationStatus.PENDING)
                .first()
            )
            if not locked:
                return _gone()

            user = existing
            if user is None:
                user = User.objects.create_user(
                    username=invitation.email,
                    email=invitation.email,
                    password=password,
                    role=UserRole.STUDENT,
                )
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])

            # Only a firm the instructor pre-assigned on the invitation. A
            # student who arrives without one stays UNALLOCATED: which firm a
            # student belongs to is a teaching decision, and auto-filling the
            # emptiest one quietly made it for them. Until an instructor
            # allocates, the student can watch the tour and nothing else.
            team = locked.team
            if team is not None:
                team.members.add(user)

            Enrollment.objects.get_or_create(
                cohort=cohort, student=user, defaults={'team': team},
            )
            enrollment = Enrollment.objects.filter(cohort=cohort, student=user).first()
            if enrollment and team is not None and enrollment.team_id != team.id:
                enrollment.team = team
                enrollment.save(update_fields=['team'])

            locked.status = InvitationStatus.ACCEPTED
            locked.accepted_at = timezone.now()
            locked.accepted_by = user
            locked.save(update_fields=['status', 'accepted_at', 'accepted_by'])

        return Response({
            'cohort_id': cohort.id,
            'cohort': cohort.name,
            'firm': team.name if team else None,
            'email': invitation.email,
            'had_account': existing is not None,
        }, status=201)


# ---- cohort self-registration ---------------------------------------------
#
# The other way in: an instructor shares one reusable link for the whole cohort
# rather than inviting addresses individually. The instructor console has always
# generated this link (/register/<cohort token>) — nothing ever served it, so
# every shared link was a dead page.
#
# Unlike an invitation, this token is reusable and not tied to an address, so
# the student supplies their own email and it is checked against capacity.


def _open_cohort(token):
    if not token:
        return None
    return Cohort.objects.filter(registration_token=token).first()


def _seat_student(cohort, user, preferred_team=None):
    """Enroll a student, leaving them unallocated unless a firm was named.

    Firm allocation is the instructor's call — they balance firms, separate
    people who shouldn't work together, and sometimes wait for the roster to
    settle. Auto-filling the emptiest firm took that decision away and did it
    silently, at the moment of registration.
    """
    team = preferred_team
    if team is not None:
        team.members.add(user)
    enrollment, _ = Enrollment.objects.get_or_create(
        cohort=cohort, student=user, defaults={'team': team},
    )
    if team is not None and enrollment.team_id != getattr(team, 'id', None):
        enrollment.team = team
        enrollment.save(update_fields=['team'])
    return team


class RegistrationDetailView(APIView):
    """What cohort does this shared link join you to?"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        cohort = _open_cohort(token)
        if not cohort:
            return Response(
                {'detail': 'This registration link is not valid. Ask your instructor for a current one.'},
                status=404,
            )
        enrolled = Enrollment.objects.filter(cohort=cohort).count()
        capacity = cohort.enrollment_capacity or 0
        return Response({
            'cohort': cohort.name,
            'tier': cohort.tier,
            'start_date': cohort.start_date.isoformat() if cohort.start_date else None,
            'total_rounds': 14,
            'seats_left': max(0, capacity - enrolled) if capacity else None,
            'full': bool(capacity and enrolled >= capacity),
        })


class RegistrationAcceptView(APIView):
    """Join a cohort through its shared link."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        cohort = _open_cohort(token)
        if not cohort:
            return Response(
                {'detail': 'This registration link is not valid. Ask your instructor for a current one.'},
                status=404,
            )

        errors = {}
        email = (request.data.get('email') or '').strip().lower()
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()
        password = request.data.get('password') or ''
        confirm = request.data.get('password_confirm') or ''

        if not email or '@' not in email:
            errors['email'] = 'Enter the email address you use for this course.'
        if not first_name:
            errors['first_name'] = 'Tell us your first name.'

        existing = User.objects.filter(username__iexact=email).first() if email else None
        if email and not existing:
            if len(password) < MIN_PASSWORD_LENGTH:
                errors['password'] = f'Use at least {MIN_PASSWORD_LENGTH} characters.'
            elif confirm and password != confirm:
                errors['password_confirm'] = 'The two passwords do not match.'
        if errors:
            return Response({'detail': 'Some fields need attention.', 'errors': errors}, status=400)

        if existing and Enrollment.objects.filter(cohort=cohort, student=existing).exists():
            return Response(
                {'detail': 'You are already enrolled in this simulation — just sign in.'},
                status=409,
            )

        with transaction.atomic():
            capacity = cohort.enrollment_capacity or 0
            if capacity and Enrollment.objects.filter(cohort=cohort).count() >= capacity:
                return Response(
                    {'detail': 'This simulation is full. Ask your instructor to make room.'},
                    status=409,
                )

            user = existing
            if user is None:
                user = User.objects.create_user(
                    username=email, email=email, password=password, role=UserRole.STUDENT,
                )
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.save(update_fields=['first_name', 'last_name'])

            team = _seat_student(cohort, user)

            # If they were also invited by address, that invite is now spent.
            Invitation.objects.filter(
                cohort=cohort, email__iexact=email, status=InvitationStatus.PENDING,
            ).update(
                status=InvitationStatus.ACCEPTED, accepted_at=timezone.now(), accepted_by=user,
            )

        return Response({
            'cohort_id': cohort.id,
            'cohort': cohort.name,
            'firm': team.name if team else None,
            'email': email,
            'had_account': existing is not None,
        }, status=201)
