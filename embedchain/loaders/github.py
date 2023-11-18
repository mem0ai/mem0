import concurrent.futures
import hashlib
import logging
import os

from tqdm import tqdm

from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.json import JSONLoader
from embedchain.loaders.mdx import MdxLoader
from embedchain.utils import detect_datatype


def _load_file_data(path):
    data = []
    data_content = []
    try:
        with open(path, "rb") as f:
            content = f.read().decode("utf-8")
    except Exception as e:
        print(f"Error reading file {path}: {e}")
        raise ValueError(f"Failed to read file {path}")

    meta_data = {}
    meta_data["url"] = path
    data.append(
        {
            "content": content,
            "meta_data": meta_data,
        }
    )
    data_content.append(content)
    doc_id = hashlib.sha256((" ".join(data_content) + path).encode()).hexdigest()
    return {
        "doc_id": doc_id,
        "data": data,
    }


class GithubLoader(BaseLoader):
    def load_data(self, repo_url):
        """Load data from a git repo."""
        try:
            from git import Repo
        except ImportError as e:
            raise ValueError(
                "GithubLoader requires extra dependencies. Install with `pip install --upgrade 'embedchain[git]'`"
            ) from e

        mdx_loader = MdxLoader()
        json_loader = JSONLoader()
        data = []
        data_urls = []

        def _fetch_or_clone_repo(repo_url: str, local_path: str):
            if os.path.exists(local_path):
                logging.info("Repository already exists. Fetching updates...")
                repo = Repo(local_path)
                origin = repo.remotes.origin
                origin.fetch()
                logging.info("Fetch completed.")
            else:
                logging.info("Cloning repository...")
                Repo.clone_from(repo_url, local_path)
                logging.info("Clone completed.")

        def _load_file(file_path: str):
            try:
                data_type = detect_datatype(file_path).value
            except Exception:
                data_type = "unstructured"

            if data_type == "mdx":
                data = mdx_loader.load_data(file_path)
            elif data_type == "json":
                data = json_loader.load_data(file_path)
            else:
                data = _load_file_data(file_path)

            return data.get("data", [])

        def _is_file_empty(file_path):
            return os.path.getsize(file_path) == 0

        def _is_whitelisted(file_path):
            whitelisted_extensions = ["md", "txt", "html", "json", "py", "js", "jsx", "ts", "tsx", "mdx", "rst"]
            _, file_extension = os.path.splitext(file_path)
            return file_extension[1:] in whitelisted_extensions

        def _add_repo_files(repo_path: str):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_file = {
                    executor.submit(_load_file, os.path.join(root, filename)): os.path.join(root, filename)
                    for root, _, files in os.walk(repo_path)
                    for filename in files
                    if _is_whitelisted(os.path.join(root, filename))
                    and not _is_file_empty(os.path.join(root, filename))  # noqa:E501
                }
                for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(future_to_file)):
                    file = future_to_file[future]
                    try:
                        results = future.result()
                        if results:
                            data.extend(results)
                            data_urls.extend([result.get("meta_data").get("url") for result in results])
                    except Exception as e:
                        logging.warn(f"Failed to process {file}: {e}")

        source_hash = hashlib.sha256(repo_url.encode()).hexdigest()
        repo_path = f"/tmp/{source_hash}"
        _fetch_or_clone_repo(repo_url=repo_url, local_path=repo_path)
        _add_repo_files(repo_path)
        doc_id = hashlib.sha256((repo_url + ", ".join(data_urls)).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
