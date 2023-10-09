import os
import tempfile
import urllib

from PIL import Image

from embedchain.models.clip_processor import ClipProcessor


class TestClipProcessor:
    def test_load_model(self):
        # Test that the `load_model()` method loads the CLIP model and image preprocessing correctly.
        model = ClipProcessor.load_model()
        assert model is not None

    def test_get_image_features(self):
        # Clone the image to a temporary folder.
        with tempfile.TemporaryDirectory() as tmp_dir:
            urllib.request.urlretrieve("https://upload.wikimedia.org/wikipedia/en/a/a9/Example.jpg", "image.jpg")

            image = Image.open("image.jpg")
            image.save(os.path.join(tmp_dir, "image.jpg"))

            # Get the image features.
            model = ClipProcessor.load_model()
            ClipProcessor.get_image_features(os.path.join(tmp_dir, "image.jpg"), model)

            # Delete the temporary file.
            os.remove(os.path.join(tmp_dir, "image.jpg"))

    def test_get_text_features(self):
        # Test that the `get_text_features()` method returns a list containing the text embedding.
        query = "This is a text query."
        text_features = ClipProcessor.get_text_features(query)

        # Assert that the text embedding is not None.
        assert text_features is not None

        # Assert that the text embedding is a list of floats.
        assert isinstance(text_features, list)

        # Assert that the text embedding has the correct length.
        assert len(text_features) == 512
