from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.state import SCORE_DIMENSIONS


class ScoreRecord(models.Model):
    week_instance = models.OneToOneField(
        'weeks.WeekInstance',
        on_delete=models.CASCADE,
        related_name='score',
    )
    strategic_judgment = models.IntegerField(default=0)
    execution_consequence = models.IntegerField(default=0)
    coherence = models.IntegerField(default=0)
    deliverable_quality = models.IntegerField(default=0)
    auto_components = models.JSONField(default=dict)
    instructor_components = models.JSONField(default=dict)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_scores',
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def dimension_scores(self):
        return {dimension: getattr(self, dimension) for dimension in SCORE_DIMENSIONS}

    def clean(self):
        super().clean()
        for dimension in SCORE_DIMENSIONS:
            value = getattr(self, dimension)
            if value < 0:
                raise ValidationError({dimension: 'Score dimensions cannot be negative.'})

    def __str__(self):
        return f'Score for {self.week_instance}'


class Benchmark(models.Model):
    cohort = models.ForeignKey('core.Cohort', on_delete=models.CASCADE, related_name='benchmarks')
    after_week = models.PositiveSmallIntegerField()
    standings = models.JSONField(default=list)
    revealed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('cohort', 'after_week')]
        ordering = ['cohort__name', 'after_week']

    @property
    def is_revealed(self):
        return self.revealed_at is not None

    def __str__(self):
        return f'{self.cohort} after week {self.after_week}'

# Create your models here.
