from django.contrib import admin
from django.utils import timezone

from .models import Benchmark, ScoreRecord
from .services import finalize_score


@admin.action(description='Finalize selected score records')
def finalize_scores(modeladmin, request, queryset):
    for score in queryset:
        finalize_score(score, graded_by=request.user)


@admin.register(ScoreRecord)
class ScoreRecordAdmin(admin.ModelAdmin):
    list_display = (
        'week_instance',
        'strategic_judgment',
        'execution_consequence',
        'coherence',
        'deliverable_quality',
        'graded_at',
    )
    list_filter = ('graded_at', 'week_instance__week_number')
    readonly_fields = ('created_at', 'updated_at')
    actions = [finalize_scores]


@admin.action(description='Reveal selected benchmarks')
def reveal_benchmarks(modeladmin, request, queryset):
    queryset.update(revealed_at=timezone.now())


@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ('cohort', 'after_week', 'revealed_at')
    list_filter = ('after_week', 'revealed_at')
    actions = [reveal_benchmarks]

# Register your models here.
