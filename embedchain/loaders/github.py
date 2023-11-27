import concurrent.futures
import hashlib
import logging
import os
import time
from collections import defaultdict
from typing import Any, Dict, Optional

import requests
from tqdm import tqdm

from embedchain.constants import GITHUB_URL
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


class GithubLoader(BaseLoader):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()

        self.config = config if config else {}
        self.base_url = self.config.get("base_url", "https://api.github.com")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        github_username = self.config.get("username")
        token = self.config.get("token")
        if github_username and token:
            self.headers["Authorization"] = f"Basic {github_username}:{token}"

    def _parse_github_query(self, url):
        if not url or not isinstance(url, str):
            raise ValueError(
                "GithubLoader requires a valid url. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )
        query = url.split("/")[2:]
        domain = query.pop(0)
        if domain != "github.com":
            raise ValueError(
                "GithubLoader requires a valid github url. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )

        if len(query) < 2:
            raise ValueError(
                "GithubLoader requires a valid url. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )
        return "/".join(query)

    def _get_repo_file_paths(self, repo_url):
        try:
            from git import Repo
        except ImportError as e:
            raise ValueError(
                "GithubLoader requires extra dependencies to load repo data. Install with `pip install --upgrade 'embedchain[git]'`"  # noqa: E501
            ) from e

        paths = []

        def _get_repo_tree(repo_url: str, local_path: str):
            if os.path.exists(local_path):
                logging.info("Repository already exists. Fetching updates...")
                repo = Repo(local_path)
                origin = repo.remotes.origin
                origin.fetch()
                logging.info("Fetch completed.")
            else:
                logging.info("Cloning repository...")
                repo = Repo.clone_from(repo_url, local_path)
                logging.info("Clone completed.")
            return repo.head.commit.tree

        def _get_file_paths_from_git(repo_path, tree):
            for entry in tree:
                if entry.type == "tree":
                    _get_file_paths_from_git(repo_path, entry)
                else:
                    paths.append(f"{repo_path}/{entry.path}")

        repo_name = repo_url.split("/")[-1]
        repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()
        repo_path = f"/tmp/{repo_hash}/{repo_name}"
        tree = _get_repo_tree(repo_url, repo_path)
        _get_file_paths_from_git(repo_path, tree)
        return paths

    def _get_github_actions(self, urls):
        actions = defaultdict(list)
        for url in urls:
            parsed_url = self._parse_github_query(url)
            url_paths = parsed_url.split("/")
            owner, repo = url_paths[0], url_paths[1]
            data_url = f"{self.base_url}/repos"
            action = "repo"
            if any(keyword in parsed_url for keyword in ["pulls", "issues"]):
                data_url += f"/{parsed_url}"
                if "pulls" in parsed_url:
                    action = "pulls"
                elif "issues" in parsed_url:
                    action = "issues"
                actions[url].append((action, data_url))
            elif len(url_paths) == 2:
                # its a repo url
                repo_url = f"{GITHUB_URL}/{owner}/{repo}"
                logging.info(f"[INFO] Fetching all files from github repo: {repo_url}")
                file_paths = self._get_repo_file_paths(repo_url)
                action = "repo"
                for path in file_paths:
                    actions[url].append((action, path))
            else:
                raise ValueError(
                    "Github loader does not support this url. Please check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
                )
        return actions

    def _get_github_repo_data(self, path):
        url = f"{GITHUB_URL}/{'/'.join(path.split('/')[3:])}"
        try:
            with open(path, "r") as f:
                content = f.read()
                return [
                    {
                        "content": clean_string(content),
                        "meta_data": {"url": url},
                    }
                ]
        except Exception:
            logging.info(f"Could not read file at url: {url}")
            return None

    def _get_github_api_data(self, url):
        time.sleep(1.0)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == 200:
            response = response.json()
            if isinstance(response, list):
                data = []
                for item in response:
                    title = item.pop("title")
                    body = item.pop("body")
                    format_content = f"Title: {title}\nDescription: {body}"
                    meta_data = {"url": url}
                    # should we add other meta data here?
                    # meta_data.update(item)
                    data.append(
                        {
                            "content": clean_string(format_content),
                            "meta_data": meta_data,
                        }
                    )
                return data
            else:
                title = item.pop("title")
                body = item.pop("body")
                format_content = f"Title: {title}\nDescription: {body}"
                meta_data = {"url": url}
                # should we add other meta data here?
                # meta_data.update(item)
                return [
                    {
                        "content": clean_string(format_content),
                        "meta_data": meta_data,
                    }
                ]
        else:
            logging.info(f"[INFO] Failed to fetch data for {url}")
            return None

    def _get_github_data(self, action):
        type = action[0]
        url = action[1]

        if type == "repo":
            data = self._get_github_repo_data(url)
        elif type == "pulls":
            data = self._get_github_api_data(url)
        elif type == "issues":
            data = self._get_github_api_data(url)
        else:
            raise ValueError("Invalid action type")

        return data

    def load_data(self, urls):
        """Load data from github urls."""
        # self._check_input_urls(urls)
        urls = urls.split(" ") if isinstance(urls, str) else urls
        actions = self._get_github_actions(urls)
        data = []
        data_urls = []
        for url in urls:
            if url not in actions:
                logging.info(f"[INFO] No data found for {url}")
                continue

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(self._get_github_data, action): action for action in actions[url]}
                for future in tqdm(
                    concurrent.futures.as_completed(futures),
                    total=len(futures),
                    desc=f"Fetching data from github for {url}",
                ):
                    github_data = future.result()
                    if github_data:
                        data.extend(github_data)
                        metadata = [mdata.get("meta_data") for mdata in github_data]
                        data_urls.extend([durls.get("url") for durls in metadata])

        doc_id = hashlib.sha256((str(urls) + ", ".join(data_urls)).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
