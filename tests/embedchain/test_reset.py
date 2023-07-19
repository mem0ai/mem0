import unittest

from embedchain import App


class TestAppReset(unittest.TestCase):
    def test_query_after_reset(self):
        """
        Test if the `App` instance is correctly reconstructed after a reset.
        """
        app = App()
        app.reset()

        # Make sure the client is still healthy
        app.db_client.heartbeat()
        # Make sure the collection exists, and can be added to
        app.collection.add(
            embeddings=[[1.1, 2.3, 3.2], [4.5, 6.9, 4.4], [1.1, 2.3, 3.2]],
            metadatas=[
                {"chapter": "3", "verse": "16"},
                {"chapter": "3", "verse": "5"},
                {"chapter": "29", "verse": "11"},
            ],
            ids=["id1", "id2", "id3"],
        )

        app.reset()
