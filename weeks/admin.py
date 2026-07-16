from django.contrib import admin

from .models import Submission, WeekDefinition, WeekInstance


@admin.register(WeekDefinition)
class WeekDefinitionAdmin(admin.ModelAdmin):
    list_display = ('week_number', 'title', 'module_path', 'active')
    list_filter = ('active',)
    search_fields = ('title', 'module_path')


@admin.register(WeekInstance)
class WeekInstanceAdmin(admin.ModelAdmin):
    list_display = ('run', 'week_number', 'status', 'briefing_viewed_at')
    list_filter = ('status', 'week_number')
    search_fields = ('run__team__name',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('week_instance', 'submitted_by', 'submitted_at')
    readonly_fields = ('submitted_at',)

# Register your models here.
