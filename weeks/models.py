from django.conf import settings
from django.db import models


class WeekInstanceStatus(models.TextChoices):
    BRIEFING = 'BRIEFING', 'Briefing'
    CONSULTATION = 'CONSULTATION', 'Consultation'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    SCORED = 'SCORED', 'Scored'


class WeekDefinition(models.Model):
    week_number = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=255)
    module_path = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['week_number']

    def __str__(self):
        return f'Week {self.week_number}: {self.title}'


class WeekInstance(models.Model):
    run = models.ForeignKey('core.Run', on_delete=models.CASCADE, related_name='week_instances')
    week_number = models.PositiveSmallIntegerField()
    briefing_viewed_at = models.DateTimeField(null=True, blank=True)
    submission = models.OneToOneField(
        'Submission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_week_instance',
    )
    score_record = models.OneToOneField(
        'scoring.ScoreRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_week_instance',
    )
    status = models.CharField(
        max_length=20,
        choices=WeekInstanceStatus.choices,
        default=WeekInstanceStatus.BRIEFING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('run', 'week_number')]
        ordering = ['run_id', 'week_number']

    def __str__(self):
        return f'{self.run} week {self.week_number}'


class Submission(models.Model):
    week_instance = models.OneToOneField(
        WeekInstance,
        on_delete=models.CASCADE,
        related_name='submitted_payload',
    )
    structured_payload = models.JSONField(default=dict)
    deliverable_text = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Submission for {self.week_instance}'

# Create your models here.
