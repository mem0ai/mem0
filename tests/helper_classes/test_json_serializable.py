import random
import unittest

from embedchain.helper_classes.json_serializable import (
    JSONSerializable, register_deserializable)


class TestJsonSerializable(unittest.TestCase):
    """Test that the datatype detection is working, based on the input."""

    def test_base_function(self):
        """Test that the base premise of serialization and deserealization is working"""

        @register_deserializable
        class TestClass(JSONSerializable):
            def __init__(self):
                self.rng = random.random()

            def bark(self):
                print(self.rng)

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
