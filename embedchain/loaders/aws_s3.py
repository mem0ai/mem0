import hashlib
import logging
import tempfile
import os
from typing import Any, Optional

from embedchain.loaders.base_loader import BaseLoader

class S3BucketLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY", config.get("aws_access_key", ""))
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", config.get("aws_secret_access_key", ""))
        if not self.aws_access_key or not self.aws_secret_access_key:
            raise ValueError(
                "Must provide the aws access key and secret access key.",
                "Check `https://docs.embedchain.ai/components/data-sources/aws-s3` for more details."
            )
        if config:
            self.aws_session_token = config.get("aws_session_token", "")
            self.s3_endpoint_url = config.get("s3_endpoint_url", "")

    def load_data(self, query):
        """Load data from S3 bucket."""
        pass
