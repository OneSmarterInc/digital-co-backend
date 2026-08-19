from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone as dj_timezone
import uuid
from .state import default_run_state, validate_run_state


class Tier(models.TextChoices):
    UNDERGRAD = 'UNDERGRAD', 'Undergraduate'
    GRADUATE = 'GRADUATE', 'Graduate'


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    STUDENT = 'STUDENT', 'Student'
    INSTRUCTOR = 'INSTRUCTOR', 'Instructor'


class RunStatus(models.TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', 'In progress'
    COMPLETE = 'COMPLETE', 'Complete'


class TierOutcome(models.TextChoices):
    TRIUMPH = 'TRIUMPH', 'Triumph'
    WIN_WITH_SCARS = 'WIN_WITH_SCARS', 'Win with scars'
    SQUEAK_THROUGH = 'SQUEAK_THROUGH', 'Squeak through'
    DISASTER = 'DISASTER', 'Disaster'


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
    )


# Dollars per started hour of advisor time, for a cohort nobody has priced by
# hand. Instructors can still change it per cohort.
DEFAULT_ADVISOR_HOURLY_RATE = 300


class Cohort(models.Model):
    name = models.CharField(max_length=255)
    tier = models.CharField(
        max_length=20,
        choices=Tier.choices,
        default=Tier.UNDERGRAD,
    )
    current_phase = models.PositiveSmallIntegerField(default=0)
    timezone = models.CharField(max_length=64, default='UTC')
    start_date = models.DateField(null=True, blank=True)
    deployed_for_faculty_at = models.DateTimeField(null=True, blank=True)
    deployed_for_students_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=dj_timezone.now)
    team_size = models.PositiveSmallIntegerField(default=4)          # students per team
    days_per_week = models.PositiveSmallIntegerField(default=7)      # phase pacing
    enrollment_capacity = models.PositiveIntegerField(default=30)    # max students
    price_per_student = models.PositiveIntegerField(default=0)       # billing rate, 0 = free
    # Per started hour of advisor chat. A war-room hour bills this once per
    # advisor in the room, so four advisors for an hour is 4x this figure.
    #
    # This defaults to the real rate rather than 0 on purpose: advisor scarcity
    # is what forces triage, and the war-room UI only shows cost when the rate
    # is above zero. A cohort created with 0 would look like it was working
    # while quietly making consultation free.
    advisor_hourly_rate = models.PositiveIntegerField(default=DEFAULT_ADVISOR_HOURLY_RATE)
    registration_token = models.CharField(max_length=64, blank=True, default='')
    round_extensions = models.JSONField(default=dict, blank=True)  # {round_number: extra_days} added when a round is extended
    instructors = models.ManyToManyField(
        User,
        related_name='instructed_cohorts',
        blank=True,
        limit_choices_to={'role': UserRole.INSTRUCTOR},
    )

    @property
    def deployment_status(self):
        if self.deployed_for_students_at:
            return 'students'
        if self.deployed_for_faculty_at:
            return 'faculty'
        return 'draft'
    
    def __str__(self):
        return self.name


class Team(models.Model):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(
        User,
        related_name='teams',
        blank=True,
        limit_choices_to={'role': UserRole.STUDENT},
    )

    class Meta:
        unique_together = [('cohort', 'name')]
        ordering = ['cohort__name', 'name']

    def __str__(self):
        return f'{self.cohort}: {self.name}'


class Run(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='run')
    current_week = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.IN_PROGRESS,
    )
    state = models.JSONField(default=default_run_state)
    tier_outcome = models.CharField(
        max_length=30,
        choices=TierOutcome.choices,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        validate_run_state(self.state)
        if not 1 <= self.current_week <= 14:
            raise ValidationError({'current_week': 'Current week must be between 1 and 14.'})

    def save(self, *args, **kwargs):
        if self.state is None:
            self.state = default_run_state()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.team} run'

class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    EXPIRED = 'EXPIRED', 'Expired'


class Invitation(models.Model):
    """An email invite for a student to join a cohort.

    Students simply belong to a team, so an invite may pre-assign a team but
    carries no executive seat. One outstanding invite per (cohort, email).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True)
    cohort = models.ForeignKey(
        Cohort,
        related_name='invitations',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    team = models.ForeignKey(
        Team,
        related_name='invitations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    # Delivery is recorded so an instructor can see who actually received the
    # email rather than only who was added to the list.
    sent_at = models.DateTimeField(null=True, blank=True)
    send_error = models.CharField(max_length=500, blank=True, default='')
    invited_by = models.ForeignKey(
        User,
        related_name='invitations_sent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        related_name='invitations_accepted',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cohort', 'email'],
                name='uniq_cohort_email_invitation',
            ),
        ]

    def __str__(self):
        return f'Invite {self.email} -> {self.cohort}'


class Enrollment(models.Model):
    """A student's membership in a cohort, plus the billing and access state an
    instructor controls.

    Team membership is mirrored onto Team.members when a team is set, so the
    existing flows that read team.members keep working unchanged.
    """
    cohort = models.ForeignKey(Cohort, related_name='enrollments', on_delete=models.CASCADE)
    student = models.ForeignKey(User, related_name='enrollments', on_delete=models.CASCADE)
    team = models.ForeignKey(
        Team,
        related_name='enrollments',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    amount_due = models.PositiveIntegerField(default=0)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('cohort', 'student')]
        ordering = ['team__name', 'student__username']

    def __str__(self):
        state = 'paid' if self.paid else 'unpaid'
        return f'{self.student} in {self.cohort} ({state})'