"""Offline backend contracts; no Hermes install, credentials, or database needed."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

spec = importlib.util.spec_from_file_location("hermes_backend_test._backend", Path(__file__).parents[1] / "_backend.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class BackendTests(unittest.TestCase):
    def test_cloud_and_oss_preserve_scope_and_accept_optional_session(self):
        for backend_type, client_attr in ((backend.PlatformBackend, "_client"), (backend.OSSBackend, "_memory")):
            with self.subTest(backend=backend_type.__name__):
                instance = backend_type.__new__(backend_type)
                client = Mock()
                setattr(instance, client_attr, client)
                client.search.return_value = {"results": [{"id": "old", "memory": "Legacy memory"}]}
                instance.add([{"role": "user", "content": "fact"}], user_id="user", agent_id="hermes")
                self.assertNotIn("run_id", client.add.call_args.kwargs)
                instance.add([], user_id="user", agent_id="hermes", run_id="session", metadata={"channel": "cli"})
                self.assertEqual(client.add.call_args.kwargs["run_id"], "session")
                self.assertEqual(client.add.call_args.kwargs["metadata"], {"channel": "cli"})
                self.assertEqual(instance.search("fact", filters={"user_id": "user"}, top_k=3)[0]["id"], "old")
                self.assertEqual(client.search.call_args.kwargs["filters"], {"user_id": "user"})
                self.assertEqual(client.search.call_args.kwargs["top_k"], 3)

    def test_selfhosted_http_contract(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"results": [{"id": "legacy", "memory": "fact"}]})

        instance = backend.SelfHostedBackend(
            "test-key", "http://localhost:8888/", transport=httpx.MockTransport(respond)
        )
        try:
            instance.add([], user_id="user", agent_id="hermes", run_id="session", infer=True)
            self.assertEqual(json.loads(requests[-1].content)["run_id"], "session")
            self.assertEqual(requests[-1].headers["X-API-Key"], "test-key")
            instance.search("fact", filters={"user_id": "user"}, top_k=7, rerank=True)
            self.assertEqual(str(requests[-1].url), "http://localhost:8888/search")
            self.assertEqual(
                json.loads(requests[-1].content), {"query": "fact", "filters": {"user_id": "user"}, "top_k": 7}
            )
            instance.update("legacy", "new fact")
            self.assertEqual((requests[-1].method, json.loads(requests[-1].content)), ("PUT", {"text": "new fact"}))
            instance.delete("legacy")
            self.assertEqual(requests[-1].method, "DELETE")
        finally:
            instance.close()

    def test_qdrant_dimension_change_never_deletes_memories(self):
        client = Mock()
        client.collection_exists.return_value = True
        client.get_collection.return_value.config.params.vectors = SimpleNamespace(size=1536)
        with patch.dict(sys.modules, {"qdrant_client": SimpleNamespace(QdrantClient=Mock(return_value=client))}):
            with self.assertRaisesRegex(ValueError, "1536.*768"):
                backend.OSSBackend._recreate_collection_if_dims_changed("qdrant", {"path": "/unused"}, 768)
        client.delete_collection.assert_not_called()
        client.close.assert_called_once()

    def test_pgvector_dimension_change_never_drops_table(self):
        cursor = Mock()
        cursor.fetchone.return_value = (1536,)
        connection = Mock()
        connection.cursor.return_value = cursor
        driver = SimpleNamespace(connect=Mock(return_value=connection), sql=Mock())
        with patch.dict(sys.modules, {"psycopg2": driver}):
            with self.assertRaisesRegex(ValueError, "1536.*768"):
                backend.OSSBackend._recreate_collection_if_dims_changed("pgvector", {"user": "test"}, 768)
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertTrue(cursor.execute.call_args.args[0].startswith("SELECT"))
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
