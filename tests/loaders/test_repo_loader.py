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
