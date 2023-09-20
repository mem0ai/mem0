import json
import random
import unittest
from string import Template

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig
from embedchain.helper.json_serializable import (JSONSerializable,
                                                 register_deserializable)


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

    def test_full_serialization(self):
        """Tests that the app object is fully identical"""

        def get_nested_vars(obj, depth=5):
            """Recursively retrieves vars() for all attributes of an object up to a specified depth."""
            if depth <= 0:
                return str(type(obj))  # or some other representation when max depth is reached

            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj

            if isinstance(obj, list):
                return [get_nested_vars(item, depth=depth - 1) for item in obj]

            if isinstance(obj, dict):
                return {key: get_nested_vars(value, depth=depth - 1) for key, value in obj.items()}

            if isinstance(obj, set):
                return list(obj)  # Convert the set to a list for JSON serialization

            try:
                attributes = vars(obj).copy()  # Use copy to prevent modifying the original object
                for attr, value in attributes.items():
                    attributes[attr] = get_nested_vars(value, depth=depth - 1)
                return attributes
            except TypeError:
                return obj

        app = App(config=None, app_config=AppConfig(collect_metrics=False))
        original_vars = get_nested_vars(app)

        serial = app.serialize()
        del app

        app = App.deserialize(serial)
        new_vars = get_nested_vars(app)

        IGNORED = {"config": ["logger"], "llm": ["memory"]}
        # s_id is not ignored because raw serialization should save it too.

        for key, value in original_vars.items():
            for k, vs in IGNORED.items():
                if key == k:
                    for v in vs:
                        del value[v]

            try:
                original_string = json.dumps(value, sort_keys=True)
            except Exception:
                original_string = ""
            try:
                new_string = json.dumps(new_vars.get(key, {}), sort_keys=True)
            except Exception:
                new_string = ""
            self.assertEqual(original_string, new_string)

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
        SecondTestClass.register_class_as_deserializable(SecondTestClass)
        app: SecondTestClass = SecondTestClass().deserialize(serial)
        self.assertFalse(app.default)

    def test_recursive(self):
        """Test recursiveness with the real app"""
        random_id = str(random.random())
        app_config = AppConfig(id=random_id, collect_metrics=False)
        # config class is set under app.config.
        app = App(config=None, app_config=app_config)
        # w/o recursion it would just be <embedchain.config.apps.OpenSourceAppConfig.OpenSourceAppConfig object at x>
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
        self.assertEqual(config.template.template, new_config.template.template)

    def test_values_with_false_default(self):
        """Values with a `false` default should not be deserialized as null."""
        app = App(config=None, app_config=AppConfig(collect_metrics=False))
        original_serial = app.db.config.serialize()
        # allow_reset is false

        # Deserialize
        app.db.config = App.deserialize(original_serial)
        self.assertEqual(app.db.config.serialize(), original_serial)

    def test_deserialize_in_place(self):
        """Tests that deserialization works in place."""
        app = App(config=None, app_config=AppConfig(collect_metrics=False))
        app.s_id = 0

        original_serial = app.serialize()

        # meanwhile, change something
        app.db.set_collection_name("new-test-collection")
        # This change should not be part of the app,
        # after it has been deserialized back to the original state.

        app.deserialize_in_place(original_serial)
        app.s_id = 0
        self.assertEqual(original_serial, app.serialize())
