import os
import subprocess
import tempfile
import unittest

from embedchain.loaders.repo_loader import RepoLoader


class TestRepoLoader(unittest.TestCase):
    def test_load_data(self):
        """
        Test the load_data function of RepoLoader using a stable GitHub repository.
        """
        repo_loader = RepoLoader()
        result = repo_loader.load_data("https://github.com/github/gitignore")

        # Verify the returned data
        # The returned data should be a list of dictionaries
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

        # Check the first item in the list
        data_item = result[0]
        self.assertIsInstance(data_item, dict)
        self.assertIn("content", data_item)
        self.assertIn("meta_data", data_item)

        # Verify the metadata
        metadata = data_item["meta_data"]
        self.assertEqual(metadata["url"], "https://github.com/github/gitignore")


class TestRepoLoaderWithLocalClone(unittest.TestCase):
    def test_load_data_from_local_clone(self):
        """
        Test the load_data function of RepoLoader using a locally cloned repository.
        """
        # Create a temporary directory for the clone
        temp_dir = tempfile.mkdtemp()

        try:
            # Clone the repository to the temporary directory
            git_url = "https://github.com/github/gitignore"
            local_repo_path = os.path.join(temp_dir, "gitignore")
            subprocess.run(["git", "clone", git_url, local_repo_path], check=True)

            # Instantiate RepoLoader and load data from the local clone
            repo_loader = RepoLoader()
            result = repo_loader.load_data(local_repo_path)

            # Verify the returned data
            # The returned data should be a list of dictionaries
            self.assertIsInstance(result, list)
            self.assertGreaterEqual(len(result), 1)

            # Check the first item in the list
            data_item = result[0]
            self.assertIsInstance(data_item, dict)
            self.assertIn("content", data_item)
            self.assertIn("meta_data", data_item)

            # Verify the metadata
            metadata = data_item["meta_data"]
            # Verify the URL is correct even when loaded locally
            self.assertEqual(metadata["url"], f"repo-{local_repo_path}")

        finally:
            # Clean up the temporary directory
            subprocess.run(["rm", "-rf", temp_dir], check=True)
