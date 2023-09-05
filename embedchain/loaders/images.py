import os
import logging
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.ClipProcessor import ClipProcessor


class ImagesLoader(BaseLoader):

    def load_data(self, image_url):
        """
        Loads images from the supplied directory/file and applies CLIP model transformation to represent these images
        in vector form

        :param image_url: The URL from which the images are to be loaded
        """
        # load model and image preprocessing
        model, preprocess = ClipProcessor.load_model()
        if os.path.isfile(image_url):
            return [
                ClipProcessor.get_image_features(image_url, model, preprocess)
            ]
        else:
            data = []
            for filename in os.listdir(image_url):
                filepath = os.path.join(image_url, filename)
                try:
                    data.append(ClipProcessor.get_image_features(filepath, model, preprocess))
                except Exception as e:
                    # Log the file that was not loaded
                    logging.exception("Failed to load the file {}. Exception {}".format(filepath, e))
            return data
