try:
    from PIL import Image, UnidentifiedImageError
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "Images requires extra dependencies. Install with `pip install 'embedchain[images]'"
    ) from None

MODEL_NAME = "clip-ViT-B-32"


class ClipProcessor:
    @staticmethod
    def load_model():
        """Load data from a director of images."""
        # load model and image preprocessing
        model = SentenceTransformer(MODEL_NAME)
        return model

    @staticmethod
    def get_image_features(image_url, model):
        """
        Applies the CLIP model to evaluate the vector representation of the supplied image
        """
        try:
            # load image
            image = Image.open(image_url)
        except FileNotFoundError:
            raise FileNotFoundError("The supplied file does not exist`")
        except UnidentifiedImageError:
            raise UnidentifiedImageError("The supplied file is not an image`")

        image_features = model.encode(image)
        meta_data = {"url": image_url}
        return {"content": image_url, "embedding": image_features.tolist(), "meta_data": meta_data}

    @staticmethod
    def get_text_features(query):
        """
        Applies the CLIP model to evaluate the vector representation of the supplied text
        """
        model = ClipProcessor.load_model()
        text_features = model.encode(query)
        return text_features.tolist()
