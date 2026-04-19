from __future__ import annotations

import unittest

from app.schemas.event import EventMessage
from app.services.ingestion import IngestionService


class IngestionServiceTests(unittest.TestCase):
    def test_normalize_messages_collapses_internal_whitespace(self) -> None:
        messages = [
            EventMessage(role="user", content="  Continue   the   migration   "),
            EventMessage(role="assistant", content=" I   updated   the docs "),
        ]

        normalized = IngestionService.normalize_messages(messages)

        self.assertEqual(
            [message.model_dump() for message in normalized],
            [
                {"role": "user", "content": "Continue the migration"},
                {"role": "assistant", "content": "I updated the docs"},
            ],
        )

    def test_compute_dedupe_key_is_deterministic(self) -> None:
        payload = {
            "messages": [{"role": "user", "content": "Continue the plan"}],
            "metadata": {"project_id": "mem-runtime"},
        }

        first = IngestionService.compute_dedupe_key(
            namespace_id="ns-1",
            agent_id="ag-1",
            session_id="run-1",
            source_system="openclaw",
            event_type="conversation_turn",
            normalized_payload=payload,
        )
        second = IngestionService.compute_dedupe_key(
            namespace_id="ns-1",
            agent_id="ag-1",
            session_id="run-1",
            source_system="openclaw",
            event_type="conversation_turn",
            normalized_payload=payload,
        )

        self.assertEqual(first, second)
