from django.contrib import admin

from .models import AdvisorDefinition, Conversation, GroupSession, GroupTurn, Message


@admin.register(AdvisorDefinition)
class AdvisorDefinitionAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'title', 'active')
    list_filter = ('active',)
    search_fields = ('key', 'name', 'title')


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('run', 'week_number', 'advisor', 'updated_at')
    list_filter = ('week_number', 'advisor')
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('content',)


class GroupTurnInline(admin.TabularInline):
    model = GroupTurn
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(GroupSession)
class GroupSessionAdmin(admin.ModelAdmin):
    list_display = ('run', 'week_number', 'created_at')
    list_filter = ('week_number',)
    inlines = [GroupTurnInline]


@admin.register(GroupTurn)
class GroupTurnAdmin(admin.ModelAdmin):
    list_display = ('session', 'speaker', 'created_at')
    search_fields = ('content',)

# Register your models here.
