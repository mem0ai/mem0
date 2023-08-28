import json

class JSONSerializable:
    """
    A class to represent a JSON serializable object.

    This class provides methods to serialize and deserialize objects,
    as well as save serialized objects to a file and load them back.
    """

    # A set of classes that are allowed to be deserialized.
    _deserializable_classes = set()

    def serialize(self):
        """
        Serialize the object to a JSON-formatted string.

        Returns:
            str: A JSON string representation of the object.
        """
        try:
            return json.dumps(self, default=self._auto_encoder, ensure_ascii=False)
        except Exception as e:
            print(f"Serialization error: {e}")
            return "{}"

    @classmethod
    def deserialize(cls, json_str):
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
    def _auto_encoder(obj):
        """
        Automatically encode an object for JSON serialization.

        Args:
            obj (Object): The object to be encoded.

        Returns:
            dict: A dictionary representation of the object.
        """
        if hasattr(obj, "__dict__"):
            dct = obj.__dict__.copy()
            dct['__class__'] = obj.__class__.__name__
            return dct
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @classmethod
    def _auto_decoder(cls, dct):
        """
        Automatically decode a dictionary to an object during JSON deserialization.

        Args:
            dct (dict): The dictionary representation of an object.

        Returns:
            Object: The decoded object or the original dictionary if decoding is not possible.
        """
        if '__class__' in dct:
            class_name = dct.pop('__class__')
            if class_name not in cls._deserializable_classes:
                print(f"Deserialization of class '{class_name}' is not allowed.")
                return {}
            target_class = next((cl for cl in cls._deserializable_classes if cl.__name__ == class_name), None)
            if target_class:
                obj = target_class.__new__(target_class)
                for key, value in dct.items():
                    default_value = getattr(target_class, key, None)
                    setattr(obj, key, value or default_value)
                return obj
        return dct

    def save_to_file(self, filename):
        """
        Save the serialized object to a file.

        Args:
            filename (str): The path to the file where the object should be saved.
        """
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.serialize())

    @classmethod
    def load_from_file(cls, filename):
        """
        Load and deserialize an object from a file.

        Args:
            filename (str): The path to the file from which the object should be loaded.

        Returns:
            Object: The deserialized object.
        """
        with open(filename, 'r', encoding='utf-8') as f:
            json_str = f.read()
            return cls.deserialize(json_str)
