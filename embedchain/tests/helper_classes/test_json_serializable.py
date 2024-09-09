import random
import unittest
from string import Template

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig
from embedchain.helpers.json_serializable import (
    JSONSerializable,
    register_deserializable,
)


class TestJsonSerializable(unittest.TestCase):
    """Test that the datatype detection is working, based on the input."""

    def test_base_function(self):
        """Test that the base premise of serialization and deserealization is working"""

        @register_deserializable
        class TestClass(JSONSerializable):
            def __init__(self):
                self.rng = random.random()

        original_class = TestClass()
        serial = original_class.serialize()

        # Negative test to show that a new class does not have the same random number.
        negative_test_class = TestClass()
        self.assertNotEqual(original_class.rng, negative_test_class.rng)

        # Test to show that a deserialized class has the same random number.
        positive_test_class: TestClass = TestClass().deserialize(serial)
        self.assertEqual(original_class.rng, positive_test_class.rng)
        self.assertTrue(isinstance(positive_test_class, TestClass))

        # Test that it works as a static method too.
        positive_test_class: TestClass = TestClass.deserialize(serial)
        self.assertEqual(original_class.rng, positive_test_class.rng)

    # TODO: There's no reason it shouldn't work, but serialization to and from file should be tested too.

    def test_registration_required(self):
        """Test that registration is required, and that without registration the default class is returned."""

        class SecondTestClass(JSONSerializable):
            def __init__(self):
                self.default = True

        app = SecondTestClass()
        # Make not default
        app.default = False
        # Serialize
        serial = app.serialize()
        # Deserialize. Due to the way errors are handled, it will not fail but return a default class.
        app: SecondTestClass = SecondTestClass().deserialize(serial)
        self.assertTrue(app.default)
        # If we register and try again with the same serial, it should work
        SecondTestClass._register_class_as_deserializable(SecondTestClass)
        app: SecondTestClass = SecondTestClass().deserialize(serial)
        self.assertFalse(app.default)

    def test_recursive(self):
        """Test recursiveness with the real app"""
        random_id = str(random.random())
        config = AppConfig(id=random_id, collect_metrics=False)
        # config class is set under app.config.
        app = App(config=config)
        s = app.serialize()
        new_app: App = App.deserialize(s)
        # The id of the new app is the same as the first one.
        self.assertEqual(random_id, new_app.config.id)
        # We have proven that a nested class (app.config) can be serialized and deserialized just the same.
        # TODO: test deeper recursion

    def test_special_subclasses(self):
        """Test special subclasses that are not serializable by default."""
        # Template
        config = BaseLlmConfig(template=Template("My custom template with $query, $context and $history."))
        s = config.serialize()
        new_config: BaseLlmConfig = BaseLlmConfig.deserialize(s)
        self.assertEqual(config.prompt.template, new_config.prompt.template)
