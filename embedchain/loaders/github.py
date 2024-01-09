import concurrent.futures
import hashlib
import logging
import os
import re
import shlex
from typing import Any, Optional

from tqdm import tqdm

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

GITHUB_URL = "https://github.com"
GITHUB_API_URL = "https://api.github.com"

VALID_SEARCH_TYPES = set(["code", "repo", "pr", "issue", "discussion"])


class GithubLoader(BaseLoader):
    """Load data from GitHub search query."""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        if not config:
            raise ValueError(
                "GithubLoader requires a personal access token to use github api. Check - `https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic`"  # noqa: E501
            )

        try:
            from github import Github
        except ImportError as e:
            raise ValueError(
                "GithubLoader requires extra dependencies. Install with `pip install --upgrade 'embedchain[github]'`"
            ) from e

        self.config = config
        token = config.get("token")
        if not token:
            raise ValueError(
                "GithubLoader requires a personal access token to use github api. Check - `https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic`"  # noqa: E501
            )

        try:
            self.client = Github(token)
        except Exception as e:
            logging.error(f"GithubLoader failed to initialize client: {e}")
            self.client = None

    def _github_search_code(self, query: str):
        """Search GitHub code."""
        data = []
        results = self.client.search_code(query)
        for result in tqdm(results, total=results.totalCount, desc="Loading code files from github"):
            url = result.html_url
            logging.info(f"Added data from url: {url}")
            content = result.decoded_content.decode("utf-8")
            metadata = {
                "url": url,
            }
            data.append(
                {
                    "content": clean_string(content),
                    "meta_data": metadata,
                }
            )
        return data

    @staticmethod
    def _get_github_repo_data(repo_url: str):
        local_hash = hashlib.sha256(repo_url.encode()).hexdigest()
        local_path = f"/tmp/{local_hash}"
        data = []

        def _get_repo_tree(repo_url: str, local_path: str):
            try:
                from git import Repo
            except ImportError as e:
                raise ValueError(
                    "GithubLoader requires extra dependencies. Install with `pip install --upgrade 'embedchain[github]'`"  # noqa: E501
                ) from e

            if os.path.exists(local_path):
                logging.info("Repository already exists. Fetching updates...")
                repo = Repo(local_path)
                logging.info("Fetch completed.")
            else:
                logging.info("Cloning repository...")
                repo = Repo.clone_from(repo_url, local_path)
                logging.info("Clone completed.")
            return repo.head.commit.tree

        def _get_repo_tree_contents(repo_path, tree, progress_bar):
            for subtree in tree:
                if subtree.type == "tree":
                    _get_repo_tree_contents(repo_path, subtree, progress_bar)
                else:
                    assert subtree.type == "blob"
                    try:
                        contents = subtree.data_stream.read().decode("utf-8")
                    except Exception:
                        logging.warning(f"Failed to read file: {subtree.path}")
                        progress_bar.update(1) if progress_bar else None
                        continue

                    url = f"{repo_url.rstrip('.git')}/blob/main/{subtree.path}"
                    data.append(
                        {
                            "content": clean_string(contents),
                            "meta_data": {
                                "url": url,
                            },
                        }
                    )
                if progress_bar is not None:
                    progress_bar.update(1)

        repo_tree = _get_repo_tree(repo_url, local_path)
        tree_list = list(repo_tree.traverse())
        with tqdm(total=len(tree_list), desc="Loading files:", unit="item") as progress_bar:
            _get_repo_tree_contents(local_path, repo_tree, progress_bar)

        return data

    def _github_search_repo(self, query: str) -> list[dict]:
        """Search GitHub repo."""
        data = []
        logging.info(f"Searching github repos with query: {query}")
        results = self.client.search_repositories(query)
        # Add repo urls and descriptions
        urls = list(map(lambda x: x.html_url, results))
        descriptions = list(map(lambda x: x.description, results))
        data.append(
            {
                "content": clean_string(desc),
                "meta_data": {
                    "url": url,
                },
            }
            for url, desc in zip(urls, descriptions)
        )

        # Add repo contents
        for result in results:
            clone_url = result.clone_url
            logging.info(f"Cloning repository: {clone_url}")
            data = self._get_github_repo_data(clone_url)
        return data

    def _github_search_issues_and_pr(self, query: str, type: str) -> list[dict]:
        """Search GitHub issues and PRs."""
        data = []

        query = f"{query} is:{type}"
        logging.info(f"Searching github for query: {query}")

        results = self.client.search_issues(query)

        logging.info(f"Total results: {results.totalCount}")
        for result in tqdm(results, total=results.totalCount, desc=f"Loading {type} from github"):
            url = result.html_url
            title = result.title
            body = result.body
            if not body:
                logging.warning(f"Skipping issue because empty content for: {url}")
                continue
            labels = " ".join([label.name for label in result.labels])
            issue_comments = result.get_comments()
            comments = []
            comments_created_at = []
            for comment in issue_comments:
                comments_created_at.append(str(comment.created_at))
                comments.append(f"{comment.user.name}:{comment.body}")
            content = "\n".join([title, labels, body, *comments])
            metadata = {
                "url": url,
                "created_at": str(result.created_at),
                "comments_created_at": " ".join(comments_created_at),
            }
            data.append(
                {
                    "content": clean_string(content),
                    "meta_data": metadata,
                }
            )
        return data

    # need to test more for discussion
    def _github_search_discussions(self, query: str):
        """Search GitHub discussions."""
        data = []

        query = f"{query} is:discussion"
        logging.info(f"Searching github repo for query: {query}")
        repos_results = self.client.search_repositories(query)
        logging.info(f"Total repos found: {repos_results.totalCount}")
        for repo_result in tqdm(repos_results, total=repos_results.totalCount, desc="Loading discussions from github"):
            teams = repo_result.get_teams()
            for team in teams:
                team_discussions = team.get_discussions()
                for discussion in team_discussions:
                    url = discussion.html_url
                    title = discussion.title
                    body = discussion.body
                    if not body:
                        logging.warning(f"Skipping discussion because empty content for: {url}")
                        continue
                    comments = []
                    comments_created_at = []
                    print("Discussion comments: ", discussion.comments_url)
                    content = "\n".join([title, body, *comments])
                    metadata = {
                        "url": url,
                        "created_at": str(discussion.created_at),
                        "comments_created_at": " ".join(comments_created_at),
                    }
                    data.append(
                        {
                            "content": clean_string(content),
                            "meta_data": metadata,
                        }
                    )
        return data

    def _search_github_data(self, search_type: str, query: str):
        """Search github data."""
        if search_type == "code":
            data = self._github_search_code(query)
        elif search_type == "repo":
            data = self._github_search_repo(query)
        elif search_type == "issue":
            data = self._github_search_issues_and_pr(query, search_type)
        elif search_type == "pr":
            data = self._github_search_issues_and_pr(query, search_type)
        elif search_type == "discussion":
            raise ValueError("GithubLoader does not support searching discussions yet.")
        else:
            raise NotImplementedError(f"{search_type} not supported")

        return data

    @staticmethod
    def _get_valid_github_query(query: str):
        """Check if query is valid and return search types and valid GitHub query."""
        query_terms = shlex.split(query)
        # query must provide repo to load data from
        if len(query_terms) < 1 or "repo:" not in query:
            raise ValueError(
                "GithubLoader requires a search query with `repo:` term. Refer docs - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )

        github_query = []
        types = set()
        type_pattern = r"type:([a-zA-Z,]+)"
        for term in query_terms:
            term_match = re.search(type_pattern, term)
            if term_match:
                search_types = term_match.group(1).split(",")
                types.update(search_types)
            else:
                github_query.append(term)

        # query must provide search type
        if len(types) == 0:
            raise ValueError(
                "GithubLoader requires a search query with `type:` term. Refer docs - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )

        for search_type in search_types:
            if search_type not in VALID_SEARCH_TYPES:
                raise ValueError(
                    f"Invalid search type: {search_type}. Valid types are: {', '.join(VALID_SEARCH_TYPES)}"
                )

        query = " ".join(github_query)

        return types, query

    def load_data(self, search_query: str, max_results: int = 1000):
        """Load data from GitHub search query."""

        if not self.client:
            raise ValueError(
                "GithubLoader client is not initialized, data will not be loaded. Refer docs - `https://docs.embedchain.ai/data-sources/github`"  # noqa: E501
            )

        search_types, query = self._get_valid_github_query(search_query)
        logging.info(f"Searching github for query: {query}, with types: {', '.join(search_types)}")

        data = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures_map = executor.map(self._search_github_data, search_types, [query] * len(search_types))
            for search_data in tqdm(futures_map, total=len(search_types), desc="Searching data from github"):
                data.extend(search_data)

        return {
            "doc_id": hashlib.sha256(query.encode()).hexdigest(),
            "data": data,
        }
