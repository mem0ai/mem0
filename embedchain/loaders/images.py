try:
    import torch
    import clip
    from PIL import Image, UnidentifiedImageError
except ImportError:
    raise ImportError("Images requires extra dependencies. Install with `pip install embedchain[community]`") from None

import os
from embedchain.loaders.base_loader import BaseLoader


class ImagesLoader(BaseLoader):
    def load_data(self, image_url):
        """Load data from a director of images."""
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # load model and image preprocessing
        model, preprocess = clip.load("ViT-B/32", device=device, jit=False)

        if os.path.isfile(image_url):
            return [
                self.get_image_features(image_url, model, preprocess, device)
            ]
        else:
            data = []
            for filename in os.listdir(image_url):
                try:
                    data.append(self.get_image_features(filename, model, preprocess, device))
                except Exception:
                    # Log the file that was not loaded
                    continue
            return data

    def get_image_features(self, image_url, model, preprocess, device):
        try:
            # load image
            image = Image.open(image_url)
        except FileNotFoundError:
            raise FileNotFoundError("The supplied file does not exist`")
        except UnidentifiedImageError:
            raise UnidentifiedImageError("The supplied file is not an image`")

            # pre-process image
        processed_image = preprocess(image).unsqueeze(0).to(device)
        image_features = str(model.encode_image(processed_image).float())
        meta_data = {
            "url": image_url
        }
        return {
            "content": image_features,
            "meta_data": meta_data
        }
