import json
import logging
from string import Template
from typing import Any, Type, TypeVar, Union

T = TypeVar("T", bound="JSONSerializable")

# NOTE: Through inheritance, all of our classes should be children of JSONSerializable. (highest level)
# NOTE: The @register_deserializable decorator should be added to all user facing child classes. (lowest level)

logger = logging.getLogger(__name__)


def register_deserializable(cls: Type[T]) -> Type[T]:
    """
    A class decorator to register a class as deserializable.

    When a class is decorated with @register_deserializable, it becomes
    a part of the set of classes that the JSONSerializable class can
    deserialize.

    Deserialization is in essence loading attributes from a json file.
    This decorator is a security measure put in place to make sure that
    you don't load attributes that were initially part of another class.

    Example:
        @register_deserializable
        class ChildClass(JSONSerializable):
            def __init__(self, ...):
                # initialization logic

    Args:
        cls (Type): The class to be registered.

    Returns:
        Type: The same class, after registration.
    """
    JSONSerializable._register_class_as_deserializable(cls)
    return cls


class JSONSerializable:
    """
    A class to represent a JSON serializable object.

    This class provides methods to serialize and deserialize objects,
    as well as to save serialized objects to a file and load them back.
    """

    _deserializable_classes = set()  # Contains classes that are whitelisted for deserialization.

    def serialize(self) -> str:
        """
        Serialize the object to a JSON-formatted string.

        Returns:
            str: A JSON string representation of the object.
        """
        try:
            return json.dumps(self, default=self._auto_encoder, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            return "{}"

    @classmethod
    def deserialize(cls, json_str: str) -> Any:
        """
        Deserialize a JSON-formatted string to an object.
        If it fails, a default class is returned instead.
        Note: This *returns* an instance, it's not automatically loaded on the calling class.

        Example:
            app = App.deserialize(json_str)

        Args:
            json_str (str): A JSON string representation of an object.

        Returns:
            Object: The deserialized object.
        """
        try:
            return json.loads(json_str, object_hook=cls._auto_decoder)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            # Return a default instance in case of failure
            return cls()

    @staticmethod
    def _auto_encoder(obj: Any) -> Union[dict[str, Any], None]:
        """
        Automatically encode an object for JSON serialization.

        Args:
            obj (Object): The object to be encoded.

        Returns:
            dict: A dictionary representation of the object.
        """
        if hasattr(obj, "__dict__"):
            dct = obj.__dict__.copy()
            for key, value in list(
                dct.items()
            ):  # We use list() to get a copy of items to avoid dictionary size change during iteration.
                try:
                    # Recursive: If the value is an instance of a subclass of JSONSerializable,
                    # serialize it using the JSONSerializable serialize method.
                    if isinstance(value, JSONSerializable):
                        serialized_value = value.serialize()
                        # The value is stored as a serialized string.
                        dct[key] = json.loads(serialized_value)
                    # Custom rules (subclass is not json serializable by default)
                    elif isinstance(value, Template):
                        dct[key] = {"__type__": "Template", "data": value.template}
                    # Future custom types we can follow a similar pattern
                    # elif isinstance(value, SomeOtherType):
                    #     dct[key] = {
                    #         "__type__": "SomeOtherType",
                    #         "data": value.some_method()
                    #     }
                    # NOTE: Keep in mind that this logic needs to be applied to the decoder too.
                    else:
                        json.dumps(value)  # Try to serialize the value.
                except TypeError:
                    del dct[key]  # If it fails, remove the key-value pair from the dictionary.

            dct["__class__"] = obj.__class__.__name__
            return dct
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @classmethod
    def _auto_decoder(cls, dct: dict[str, Any]) -> Any:
        """
        Automatically decode a dictionary to an object during JSON deserialization.

        Args:
            dct (dict): The dictionary representation of an object.

        Returns:
            Object: The decoded object or the original dictionary if decoding is not possible.
        """
        class_name = dct.pop("__class__", None)
        if class_name:
            if not hasattr(cls, "_deserializable_classes"):  # Additional safety check
                raise AttributeError(f"`{class_name}` has no registry of allowed deserializations.")
            if class_name not in {cl.__name__ for cl in cls._deserializable_classes}:
                raise KeyError(f"Deserialization of class `{class_name}` is not allowed.")
            target_class = next((cl for cl in cls._deserializable_classes if cl.__name__ == class_name), None)
            if target_class:
                obj = target_class.__new__(target_class)
                for key, value in dct.items():
                    if isinstance(value, dict) and "__type__" in value:
                        if value["__type__"] == "Template":
                            value = Template(value["data"])
                        # For future custom types we can follow a similar pattern
                        # elif value["__type__"] == "SomeOtherType":
                        #     value = SomeOtherType.some_constructor(value["data"])
                    default_value = getattr(target_class, key, None)
                    setattr(obj, key, value or default_value)
                return obj
        return dct

    def save_to_file(self, filename: str) -> None:
        """
        Save the serialized object to a file.

        Args:
            filename (str): The path to the file where the object should be saved.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.serialize())

    @classmethod
    def load_from_file(cls, filename: str) -> Any:
        """
        Load and deserialize an object from a file.

        Args:
            filename (str): The path to the file from which the object should be loaded.

        Returns:
            Object: The deserialized object.
        """
        with open(filename, "r", encoding="utf-8") as f:
            json_str = f.read()
            return cls.deserialize(json_str)

    @classmethod
    def _register_class_as_deserializable(cls, target_class: Type[T]) -> None:
        """
        Register a class as deserializable. This is a classmethod and globally shared.

        This method adds the target class to the set of classes that
        can be deserialized. This is a security measure to ensure only
        whitelisted classes are deserialized.

        Args:
            target_class (Type): The class to be registered.
        """
        cls._deserializable_classes.add(target_class)
