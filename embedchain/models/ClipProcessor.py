try:
    import torch
    import clip
    from PIL import Image, UnidentifiedImageError
except ImportError:
    raise ImportError("Images requires extra dependencies. Install with `pip install embedchain[community]`") from None

MODEL_NAME = "ViT-B/32"


class ClipProcessor:
    @staticmethod
    def load_model():
        """Load data from a director of images."""
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # load model and image preprocessing
        model, preprocess = clip.load(MODEL_NAME, device=device, jit=False)
        return model, preprocess

    @staticmethod
    def get_image_features(image_url, model, preprocess):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            # load image
            image = Image.open(image_url)
        except FileNotFoundError:
            raise FileNotFoundError("The supplied file does not exist`")
        except UnidentifiedImageError:
            raise UnidentifiedImageError("The supplied file is not an image`")

            # pre-process image
        processed_image = preprocess(image).unsqueeze(0).to(device)
        image_features = model.encode_image(processed_image).detach().numpy().tolist()[0]
        meta_data = {
            "url": image_url
        }
        return {
            "content": image_features,
            "meta_data": meta_data
        }

    @staticmethod
    def get_text_features(query):
        device = "cuda" if torch.cuda.is_available() else "cpu"

        model, preprocess = ClipProcessor.load_model()
        text = clip.tokenize(query).to(device)
        with torch.no_grad():
            text_features = model.encode_text(text).cpu().numpy().tolist()[0]
        return text_features
