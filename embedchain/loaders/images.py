import os
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.ClipProcessor import ClipProcessor


class ImagesLoader(BaseLoader):
    def load_data(self, image_url):
        # load model and image preprocessing
        model, preprocess = ClipProcessor.load_model()

        if os.path.isfile(image_url):
            return [
                ClipProcessor.get_image_features(image_url, model, preprocess)
            ]
        else:
            data = []
            for filename in os.listdir(image_url):
                try:
                    data.append(ClipProcessor.get_image_features(filename, model, preprocess))
                except Exception:
                    # Log the file that was not loaded
                    continue
            return data
