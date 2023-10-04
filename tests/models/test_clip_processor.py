import tempfile
import unittest
import os
import urllib
from PIL import Image
from embedchain.models.clip_processor import ClipProcessor


class ClipProcessorTest(unittest.TestCase):

    def test_load_model(self):
        # Test that the `load_model()` method loads the CLIP model and image preprocessing correctly.
        model, preprocess = ClipProcessor.load_model()

        # Assert that the model is not None.
        self.assertIsNotNone(model)

        # Assert that the preprocess is not None.
        self.assertIsNotNone(preprocess)

    def test_get_image_features(self):
        # Clone the image to a temporary folder.
        with tempfile.TemporaryDirectory() as tmp_dir:
            urllib.request.urlretrieve(
                'https://upload.wikimedia.org/wikipedia/en/a/a9/Example.jpg',
                "image.jpg")

            image = Image.open("image.jpg")
            image.save(os.path.join(tmp_dir, "image.jpg"))

            # Get the image features.
            model, preprocess = ClipProcessor.load_model()
            ClipProcessor.get_image_features(os.path.join(tmp_dir, "image.jpg"), model, preprocess)

            # Delete the temporary file.
            os.remove(os.path.join(tmp_dir, "image.jpg"))

            # Assert that the test passes.
            self.assertTrue(True)

    def test_get_text_features(self):
        # Test that the `get_text_features()` method returns a list containing the text embedding.
        query = "This is a text query."
        model, preprocess = ClipProcessor.load_model()

        text_features = ClipProcessor.get_text_features(query)

        # Assert that the text embedding is not None.
        self.assertIsNotNone(text_features)

        # Assert that the text embedding is a list of floats.
        self.assertIsInstance(text_features, list)

        # Assert that the text embedding has the correct length.
        self.assertEqual(len(text_features), 512)
