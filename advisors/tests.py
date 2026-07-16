from django.test import TestCase

from core.models import Cohort, Run, Team, Tier, User
from weeks.registry import registry

from .models import AdvisorDefinition, Conversation, Message, MessageRole
from .prompts import assemble_system_prompt
from .services import AdvisorService


class AdvisorServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='pw')
        self.cohort = Cohort.objects.create(name='MISX Fall 2026', tier=Tier.GRADUATE)
        self.team = Team.objects.create(cohort=self.cohort, name='Team A')
        self.team.members.add(self.user)
        self.run = Run.objects.create(team=self.team)
        self.advisor = AdvisorDefinition.objects.get(key='renata_voss')
        self.conversation = Conversation.objects.create(
            run=self.run,
            week_number=1,
            advisor=self.advisor,
        )

    def test_prompt_uses_tier_modifier(self):
        module = registry.get(1)
        prompt = assemble_system_prompt(
            self.advisor,
            Tier.GRADUATE,
            module.advisor_context(self.advisor.key, Tier.GRADUATE, self.run.state),
            self.run.state,
        )
        self.assertIn('graduate', prompt.lower())
        self.assertIn('do not name frameworks', prompt)
        self.assertIn('factory-floor', prompt.lower())

    def test_respond_persists_advisor_message(self):
        Message.objects.create(
            conversation=self.conversation,
            role=MessageRole.STUDENT,
            content='What should we consider?',
        )
        module = registry.get(1)
        response = AdvisorService().respond(
            advisor=self.advisor,
            conversation=self.conversation,
            run_state=self.run.state,
            week_context=module.advisor_context(self.advisor.key, Tier.GRADUATE, self.run.state),
            tier=Tier.GRADUATE,
        )
        self.assertIn('What should we consider?', response)
        self.assertEqual(self.conversation.messages.filter(role=MessageRole.ADVISOR).count(), 1)

# Create your tests here.
