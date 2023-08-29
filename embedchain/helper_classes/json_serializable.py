import json
import logging
from typing import Any, Dict, Type, TypeVar, Union

T = TypeVar("T", bound="JSONSerializable")


def register_deserializable(cls: Type[T]) -> Type[T]:
    """
    A class decorator to register a class as deserializable.

    When a class is decorated with @register_deserializable, it becomes
    a part of the set of classes that the JSONSerializable class can
    deserialize.

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
    JSONSerializable.register_class_as_deserializable(cls)
    return cls


class JSONSerializable:
    """
    A class to represent a JSON serializable object.

    This class provides methods to serialize and deserialize objects,
    as well as save serialized objects to a file and load them back.
    """

    def __init__(self):
        # A set of classes that are allowed to be deserialized.
        # Without this, you could for instance deserialize a bot in a config.
        self._deserializable_classes: set = set()

    def serialize(self) -> str:
        """
        Serialize the object to a JSON-formatted string.

        Returns:
            str: A JSON string representation of the object.
        """
        try:
            return json.dumps(self, default=self._auto_encoder, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Serialization error: {e}")
            return "{}"

    @classmethod
    def deserialize(cls, json_str: str) -> Any:
        """
        Deserialize a JSON-formatted string to an object.

        Args:
            json_str (str): A JSON string representation of an object.

        Returns:
            Object: The deserialized object.
        """
        try:
            return json.loads(json_str, object_hook=cls._auto_decoder)
        except Exception as e:
            print(f"Deserialization error: {e}")
            # Return a default instance in case of failure
            return cls()

    @staticmethod
    def _auto_encoder(obj: Any) -> Union[Dict[str, Any], None]:
        """
        Automatically encode an object for JSON serialization.

        Args:
            obj (Object): The object to be encoded.

        Returns:
            dict: A dictionary representation of the object.
        """
        if hasattr(obj, "__dict__"):
            dct = obj.__dict__.copy()
            for key, value in list(dct.items()):  # We use list() to get a copy of items to avoid dictionary size change during iteration.
                try:
                    json.dumps(value)  # Try to serialize the value.
                except TypeError:
                    del dct[key]  # If it fails, remove the key-value pair from the dictionary.
            
            dct["__class__"] = obj.__class__.__name__
            return dct
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @classmethod
    def _auto_decoder(cls, dct: Dict[str, Any]) -> Any:
        """
        Automatically decode a dictionary to an object during JSON deserialization.

        Args:
            dct (dict): The dictionary representation of an object.

        Returns:
            Object: The decoded object or the original dictionary if decoding is not possible.
        """
        class_name = dct.pop("__class__", None)
        if class_name:
            try:
                cls._deserializable_classes
            except AttributeError:
                # If this error occurs, the decorator at the very start of this file has not been added.
                logging.error(f"`{class_name}` has no registry of allowed deserializations.")
                return {}
            if class_name not in cls._deserializable_classes:
                logging.warning(f"Deserialization of class '{class_name}' is not allowed.")
                return {}
            target_class = next((cl for cl in cls._deserializable_classes if cl.__name__ == class_name), None)
            if target_class:
                obj = target_class.__new__(target_class)
                for key, value in dct.items():
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
    def register_class_as_deserializable(cls, target_class: Type[T]) -> None:
        """
        Register a class as deserializable.

        This method adds the target class to the set of classes that
        the JSONSerializable system recognizes and allows to be deserialized.

        Args:
            target_class (Type): The class to be registered.
        """
        cls._deserializable_classes.add(target_class)
