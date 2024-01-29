import hashlib
import logging
import os
import tempfile
from typing import Any, Optional

from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.directory_loader import DirectoryLoader


class S3BucketLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY", config.get("aws_access_key", ""))
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", config.get("aws_secret_access_key", ""))
        self.aws_session_token = config.get("aws_session_token", "")
        self.s3_endpoint_url = config.get("s3_endpoint_url", "https://s3.amazonaws.com")
        self.aws_s3_region = config.get("s3_region_name", "us-east-1")

        if not self.aws_access_key or not self.aws_secret_access_key:
            logging.warning(
                "Assuming the s3 bucket is public since no aws access key and secret access key found."
            )  # noqa: E501

    def load_data(self, query):
        """Load data from S3 bucket."""
        try:
            import boto3
        except Exception as _:
            raise ModuleNotFoundError(
                "S3BucketLoader requires extra dependencies. Install with `pip install --upgrade 'embedchain[aws]'`"  # noqa: E501
            ) from None

        aws_s3 = boto3.resource(
            "s3",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.aws_s3_region,
            endpoint_url=self.s3_endpoint_url,
        )
        aws_s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.aws_s3_region,
            endpoint_url=self.s3_endpoint_url,
        )

        query_components = query.split("/", 1)
        if len(query_components) != 2:
            bucket_name = query_components[0]
            prefix = "**"
        else:
            bucket_name, prefix = query_components

        logging.info(f"Loading data from S3 bucket: {bucket_name} with prefix: {prefix}")

        aws_bucket = aws_s3.Bucket(bucket_name)
        with tempfile.TemporaryDirectory() as tmp_dir:
            for obj in aws_bucket.objects.filter(Prefix=prefix):
                local_path = f"{tmp_dir}/{obj.key}"

                check_dir = obj.key.endswith("/")
                # if the object is a directory, skip it
                if check_dir:
                    continue

                # this is needed to create the correct url in the metadata
                os.makedirs(local_path.rsplit("/", 1)[0], exist_ok=True)
                aws_s3_client.download_file(bucket_name, obj.key, local_path)

            loader = DirectoryLoader()
            loader_data = loader.load_data(tmp_dir)
            for error in loader.errors:
                print(f"printing error: {error}")

            data = []
            data_content = []
            for item in loader_data["data"]:
                content = {}
                content["content"] = item["content"]
                metadata = item["meta_data"]
                metadata["s3_bucket_name"] = bucket_name
                obj_key = metadata["url"].split("/", 1)[1]
                cloud_url = f"{self.s3_endpoint_url}/{obj_key}"
                metadata["url"] = cloud_url
                content["meta_data"] = metadata
                data.append(content)
                data_content.append(content["content"])

            doc_id = hashlib.sha256((str(data_content) + str(query)).encode()).hexdigest()
            return {
                "doc_id": doc_id,
                "data": data,
            }
