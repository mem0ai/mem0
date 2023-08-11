import unittest
from string import Template

from embedchain import App
from embedchain.config import AppConfig, QueryConfig


class TestGeneratePrompt(unittest.TestCase):
    def setUp(self):
        self.app = App(config=AppConfig(collect_metrics=False))

    def test_generate_prompt_with_template(self):
        """
        Tests that the generate_prompt method correctly formats the prompt using
        a custom template provided in the QueryConfig instance.

        This test sets up a scenario with an input query and a list of contexts,
        and a custom template, and then calls generate_prompt. It checks that the
        returned prompt correctly incorporates all the contexts and the query into
        the format specified by the template.
        """
        # Setup
        input_query = "Test query"
        contexts = ["Context 1", "Context 2", "Context 3"]
        template = "You are a bot. Context: ${context} - Query: ${query} - Helpful answer:"
        config = QueryConfig(template=Template(template))

        # Execute
        result = self.app.generate_prompt(input_query, contexts, config)

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
        config = QueryConfig()

        # Execute
        result = self.app.generate_prompt(input_query, contexts, config)

        # Assert
        expected_result = config.template.substitute(context="Context 1 | Context 2 | Context 3", query=input_query)
        self.assertEqual(result, expected_result)

    def test_generate_prompt_with_history(self):
        """
        Test the 'generate_prompt' method with QueryConfig containing a history attribute.
        """
        config = QueryConfig(history=["Past context 1", "Past context 2"])
        config.template = Template("Context: $context | Query: $query | History: $history")
        prompt = self.app.generate_prompt("Test query", ["Test context"], config)

        expected_prompt = "Context: Test context | Query: Test query | History: ['Past context 1', 'Past context 2']"
        self.assertEqual(prompt, expected_prompt)
