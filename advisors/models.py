from django.db import models


class MessageRole(models.TextChoices):
    STUDENT = 'STUDENT', 'Student'
    ADVISOR = 'ADVISOR', 'Advisor'


class AdvisorDefinition(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    persona = models.TextField()
    lane = models.TextField()
    bias = models.TextField(blank=True)
    notices = models.TextField(blank=True)
    capture_trap = models.TextField(blank=True)
    base_system_prompt = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['key']

    def save(self, *args, **kwargs):
        if not self.base_system_prompt:
            self.base_system_prompt = (
                f'You are {self.name}, {self.title}.\n'
                f'Persona: {self.persona}\n'
                f'Lane: {self.lane}\n'
                f'Bias: {self.bias}\n'
                f'Notices: {self.notices}\n'
                f'Capture trap: {self.capture_trap}'
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Conversation(models.Model):
    run = models.ForeignKey('core.Run', on_delete=models.CASCADE, related_name='conversations')
    week_number = models.PositiveSmallIntegerField()
    advisor = models.ForeignKey(AdvisorDefinition, on_delete=models.PROTECT, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def as_messages(self):
        role_map = {
            MessageRole.STUDENT: 'user',
            MessageRole.ADVISOR: 'assistant',
        }
        return [
            {'role': role_map[message.role], 'content': message.content}
            for message in self.messages.order_by('created_at', 'id')
        ]

    def __str__(self):
        return f'{self.run} week {self.week_number} with {self.advisor}'


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.role} message in {self.conversation_id}'


class AdvisorSession(models.Model):
    """One billed hour of advisor time.

    A student's first message to an advisor opens a session billed at the
    cohort's advisor_hourly_rate; further messages within the next hour ride
    along free, and the first message after that hour opens (and bills) a new
    session. The rate is snapshotted here so changing a cohort's rate later
    doesn't rewrite billing history.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='sessions')
    student = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='advisor_sessions')
    enrollment = models.ForeignKey(
        'core.Enrollment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advisor_sessions',
    )
    hourly_rate = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.student} hour in {self.conversation_id} @ {self.hourly_rate}'


class GroupSession(models.Model):
    """A war-room round: several advisors in one shared thread, talking to each
    other and not just the student.

    Scoped to a Run + week like Conversation, but deliberately kept separate
    rather than overloading it: a group turn's speaker can be the student OR any
    one of several advisors in the same thread, so there's no single fixed
    advisor. The active roster is stored as a list of AdvisorDefinition keys
    (e.g. 'diane_brandt'); the group is unbilled, so there's no AdvisorSession.
    """
    run = models.ForeignKey('core.Run', on_delete=models.CASCADE, related_name='group_sessions')
    week_number = models.PositiveSmallIntegerField()
    active_advisors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.run} week {self.week_number} group ({", ".join(self.active_advisors)})'


class GroupTurn(models.Model):
    session = models.ForeignKey(GroupSession, on_delete=models.CASCADE, related_name='turns')
    # 'student', or an AdvisorDefinition.key for the advisor who spoke.
    speaker = models.CharField(max_length=64)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.speaker} in group {self.session_id}'