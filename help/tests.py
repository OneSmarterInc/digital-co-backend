"""The channel is safe because it is starved. These tests guard the starvation,
not the model's behaviour — a prompt that never mentions the scenario cannot leak
the scenario, and that property is checkable in CI.
"""
from django.test import TestCase

from help.prompts import HELP_SYSTEM_PROMPT
from help.services import HelpService


class StarvedPromptTests(TestCase):
    # Names, figures, and storyline terms that must never reach the help channel.
    FORBIDDEN = [
        'Calloway', 'Reinhardt', 'Petrillo', 'Ferraro', 'Fischer', 'Tran',
        'Bryce', 'Diane Brandt', 'Marcus Webb', 'Renata Voss', 'Daniel Stern',
        'Frank Delgado', 'Zoe Park',
        'S/4HANA', 'telematics', 'hyperscaler', 'installed base',
        'connected products', 'black box', 'coherence anchor', 'trap',
        '40.3', '$40M', 'private equity', 'private-equity',
    ]

    def test_prompt_contains_no_scenario_content(self):
        lowered = HELP_SYSTEM_PROMPT.lower()
        found = [term for term in self.FORBIDDEN if term.lower() in lowered]
        self.assertEqual(found, [], f'scenario content leaked into the help prompt: {found}')

    def test_prompt_states_the_refusal_boundary(self):
        for phrase in ('what the student should decide', 'war room', 'How to Read a Week'):
            self.assertIn(phrase, HELP_SYSTEM_PROMPT)


class HelpServiceTests(TestCase):
    class _Spy:
        def __init__(self):
            self.system = None
            self.messages = None

        def complete(self, *, system, messages):
            self.system = system
            self.messages = messages
            return '  an answer  '

    def test_answer_sends_the_starved_prompt_and_trims(self):
        spy = self._Spy()
        self.assertEqual(HelpService(client=spy).answer('where are the exhibits?'), 'an answer')
        self.assertEqual(spy.system, HELP_SYSTEM_PROMPT)
        self.assertEqual(spy.messages, [{'role': 'user', 'content': 'where are the exhibits?'}])

    def test_blank_question_never_reaches_the_model(self):
        spy = self._Spy()
        self.assertEqual(HelpService(client=spy).answer('   '), '')
        self.assertIsNone(spy.system)

    def test_long_questions_are_clipped(self):
        spy = self._Spy()
        HelpService(client=spy).answer('x' * 5000)
        self.assertEqual(len(spy.messages[0]['content']), 600)
