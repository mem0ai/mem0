import concurrent.futures
import hashlib
import logging
import re
import shlex
from typing import Any, Optional

from tqdm import tqdm

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

GITHUB_URL = "https://github.com"
GITHUB_API_URL = "https://api.github.com"

VALID_SEARCH_TYPES = set(["code", "repo", "pr", "issue", "discussion", "branch", "file"])


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
                "GithubLoader requires extra dependencies. \
                  Install with `pip install gitpython==3.1.38 PyGithub==1.59.1`"
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

    def _get_github_repo_data(self, repo_name: str, branch_name: str = None, file_path: str = None) -> list[dict]:
        """Get file contents from Repo"""
        data = []

        repo = self.client.get_repo(repo_name)
        repo_contents = repo.get_contents("")

        if branch_name:
            repo_contents = repo.get_contents("", ref=branch_name)
        if file_path:
            repo_contents = [repo.get_contents(file_path)]

        with tqdm(desc="Loading files:", unit="item") as progress_bar:
            while repo_contents:
                file_content = repo_contents.pop(0)
                if file_content.type == "dir":
                    try:
                        repo_contents.extend(repo.get_contents(file_content.path))
                    except Exception:
                        logging.warning(f"Failed to read directory: {file_content.path}")
                        progress_bar.update(1)
                        continue
                else:
                    try:
                        file_text = file_content.decoded_content.decode()
                    except Exception:
                        logging.warning(f"Failed to read file: {file_content.path}")
                        progress_bar.update(1)
                        continue

                    file_path = file_content.path
                    data.append(
                        {
                            "content": clean_string(file_text),
                            "meta_data": {
                                "path": file_path,
                            },
                        }
                    )

                progress_bar.update(1)

        return data

    def _github_search_repo(self, query: str) -> list[dict]:
        """Search GitHub repo."""

        logging.info(f"Searching github repos with query: {query}")
        updated_query = query.split(":")[-1]
        data = self._get_github_repo_data(updated_query)
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

    def _get_github_repo_branch(self, query: str, type: str) -> list[dict]:
        """Get file contents for specific branch"""

        logging.info(f"Searching github repo for query: {query} is:{type}")
        pattern = r"repo:(\S+) name:(\S+)"
        match = re.search(pattern, query)

        if match:
            repo_name = match.group(1)
            branch_name = match.group(2)
        else:
            raise ValueError(
                f"Repository name and Branch name not found, instead found this \
                    Repo: {repo_name}, Branch: {branch_name}"
            )

        data = self._get_github_repo_data(repo_name=repo_name, branch_name=branch_name)
        return data

    def _get_github_repo_file(self, query: str, type: str) -> list[dict]:
        """Get specific file content"""

        logging.info(f"Searching github repo for query: {query} is:{type}")
        pattern = r"repo:(\S+) path:(\S+)"
        match = re.search(pattern, query)

        if match:
            repo_name = match.group(1)
            file_path = match.group(2)
        else:
            raise ValueError(
                f"Repository name and File name not found, instead found this Repo: {repo_name}, File: {file_path}"
            )

        data = self._get_github_repo_data(repo_name=repo_name, file_path=file_path)
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
        elif search_type == "branch":
            data = self._get_github_repo_branch(query, search_type)
        elif search_type == "file":
            data = self._get_github_repo_file(query, search_type)
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
