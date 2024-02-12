import unittest
from string import Template

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig


class TestGeneratePrompt(unittest.TestCase):
    def setUp(self):
        self.app = App(config=AppConfig(collect_metrics=False))

    def test_generate_prompt_with_template(self):
        """
        Tests that the generate_prompt method correctly formats the prompt using
        a custom template provided in the BaseLlmConfig instance.

        This test sets up a scenario with an input query and a list of contexts,
        and a custom template, and then calls generate_prompt. It checks that the
        returned prompt correctly incorporates all the contexts and the query into
        the format specified by the template.
        """
        # Setup
        input_query = "Test query"
        contexts = ["Context 1", "Context 2", "Context 3"]
        template = "You are a bot. Context: ${context} - Query: ${query} - Helpful answer:"
        config = BaseLlmConfig(template=Template(template))
        self.app.llm.config = config

        # Execute
        result = self.app.llm.generate_prompt(input_query, contexts)

        # Assert
        expected_result = (
            "You are a bot. Context: Context 1 | Context 2 | Context 3 - Query: Test query - Helpful answer:"
        )
        self.assertEqual(result, expected_result)

    def test_generate_prompt_with_contexts_list(self):
        """
        Tests that the generate_prompt method correctly handles a list of contexts.

        This test sets up a scenario with an input query and a list of contexts,
        and then calls generate_prompt. It checks that the returned prompt
        correctly includes all the contexts and the query.
        """
        # Setup
        input_query = "Test query"
        contexts = ["Context 1", "Context 2", "Context 3"]
        config = BaseLlmConfig()

        # Execute
        self.app.llm.config = config
        result = self.app.llm.generate_prompt(input_query, contexts)

        # Assert
        expected_result = config.prompt.substitute(context="Context 1 | Context 2 | Context 3", query=input_query)
        self.assertEqual(result, expected_result)

    def test_generate_prompt_with_history(self):
        """
        Test the 'generate_prompt' method with BaseLlmConfig containing a history attribute.
        """
        config = BaseLlmConfig()
        config.prompt = Template("Context: $context | Query: $query | History: $history")
        self.app.llm.config = config
        self.app.llm.set_history(["Past context 1", "Past context 2"])
        prompt = self.app.llm.generate_prompt("Test query", ["Test context"])

        expected_prompt = "Context: Test context | Query: Test query | History: Past context 1\nPast context 2"
        self.assertEqual(prompt, expected_prompt)
