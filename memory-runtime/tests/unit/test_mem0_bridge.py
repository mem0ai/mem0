from __future__ import annotations

import unittest

import httpx


class Mem0BridgeTests(unittest.TestCase):
    def test_http_mem0_bridge_builds_search_request_and_maps_results(self) -> None:
        from app.services.mem0_bridge import HttpMem0Bridge

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "http://mem0.test/search")
            payload = __import__("json").loads(request.content.decode("utf-8"))
            self.assertEqual(payload["query"], "what stack do we use")
            self.assertEqual(payload["agent_id"], "agent-123")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "mem0-1",
                            "memory": "Use Postgres and Redis for the durable stack.",
                            "metadata": {"space_type": "project-space"},
                        }
                    ]
                },
            )

        bridge = HttpMem0Bridge(
            base_url="http://mem0.test",
            timeout_seconds=5.0,
            transport=httpx.MockTransport(handler),
        )

        results = bridge.search(
            query="what stack do we use",
            namespace_id="namespace-1",
            agent_id="agent-123",
            limit=3,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].external_id, "mem0-1")
        self.assertEqual(results[0].space_type, "project-space")
        self.assertIn("Postgres and Redis", results[0].content)

    def test_null_mem0_bridge_returns_no_results(self) -> None:
        from app.services.mem0_bridge import NullMem0Bridge

        bridge = NullMem0Bridge()

        self.assertEqual(
            bridge.search(query="anything", namespace_id="namespace-1", agent_id="agent-1", limit=5),
            [],
        )
