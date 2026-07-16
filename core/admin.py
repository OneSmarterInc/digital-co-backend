from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Cohort, Run, Team, User


@admin.register(User)
class DigitalCoUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('DigitalCo', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = UserAdmin.list_filter + ('role',)


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'current_phase')
    list_filter = ('tier',)
    search_fields = ('name',)
    filter_horizontal = ('instructors',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'cohort')
    list_filter = ('cohort',)
    search_fields = ('name', 'cohort__name')
    filter_horizontal = ('members',)


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('team', 'current_week', 'status', 'tier_outcome')
    list_filter = ('status', 'tier_outcome', 'team__cohort__tier')
    readonly_fields = ('created_at', 'updated_at')

# Register your models here.
