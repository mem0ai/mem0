import hashlib
import logging
import os

from embedchain.loaders.base_loader import BaseLoader


class ImagesLoader(BaseLoader):
    def load_data(self, image_url):
        """
        Loads images from the supplied directory/file and applies CLIP model transformation to represent these images
        in vector form

        :param image_url: The URL from which the images are to be loaded
        """
        # load model and image preprocessing
        from embedchain.models.clip_processor import ClipProcessor

        model = ClipProcessor.load_model()
        if os.path.isfile(image_url):
            data = [ClipProcessor.get_image_features(image_url, model)]
        else:
            data = []
            for filename in os.listdir(image_url):
                filepath = os.path.join(image_url, filename)
                try:
                    data.append(ClipProcessor.get_image_features(filepath, model))
                except Exception as e:
                    # Log the file that was not loaded
                    logging.exception("Failed to load the file {}. Exception {}".format(filepath, e))
        # Get the metadata like Size, Last Modified and Last Created timestamps
        image_path_metadata = [
            str(os.path.getsize(image_url)),
            str(os.path.getmtime(image_url)),
            str(os.path.getctime(image_url)),
        ]
        doc_id = hashlib.sha256((" ".join(image_path_metadata) + image_url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
