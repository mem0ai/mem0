"""Tests for the portable memory bundle format (mem0ai/mem0#7376).

Pure-function tests (no API keys, no LLM, no vector store) plus Memory-level
tests for the export/import wiring using the same mock pattern as
tests/memory/test_main.py.
"""

from unittest.mock import MagicMock

import pytest

from mem0.memory.bundles import (
    BUNDLE_FORMAT,
    BUNDLE_VERSION,
    VerificationLevel,
    build_bundle,
    canonical_json,
    compute_digest,
    export_bundle,
    import_bundle,
    verify_bundle,
)


def _evidence(seq, outcome, exit_code=0):
    return {
        "record_id": f"ev-{seq}",
        "sequence": seq,
        "outcome": outcome,
        "operation": {
            "command": "pytest tests/ -q",
            "environment": {"os": "linux", "runtime": "python3.12"},
        },
        "result": {
            "exit_code": exit_code,
            "output_digest": "sha256:" + "a" * 64,
            "stdout_hash": None,
            "stderr_hash": None,
            "error_class": None if exit_code == 0 else "AssertionError",
        },
        "timestamp": "2026-09-28T00:00:00+00:00",
    }


def _records():
    """Bidirectional evidence: success, explicit_failure, silent_timeout."""
    return [
        {
            "memory_id": "mem-001",
            "content": "Use cmake for this project.",
            "metadata": {"user_id": "u1", "created_at": "2026-09-28T00:00:00+00:00"},
            "evidence": [_evidence(1, "success", exit_code=0)],
        },
        {
            "memory_id": "mem-002",
            "content": "Avoid rm -rf / in cleanup scripts.",
            "metadata": {"user_id": "u1", "created_at": "2026-09-28T00:00:00+00:00"},
            "evidence": [_evidence(2, "explicit_failure", exit_code=1)],
        },
        {
            "memory_id": "mem-003",
            "content": "The indexer stalled once overnight.",
            "metadata": {"user_id": "u1", "created_at": "2026-09-28T00:00:00+00:00"},
            "evidence": [_evidence(3, "silent_timeout", exit_code=124)],
        },
    ]


class TestBuildAndVerify:
    def test_round_trip_verify_passes(self):
        bundle = build_bundle(_records(), source="mem0-a", destination="mem0-b")

        assert bundle.format == BUNDLE_FORMAT
        assert bundle.version == BUNDLE_VERSION
        assert len(bundle.records) == 3
        assert len(bundle.hops) == 1
        assert bundle.hops[0].source == "mem0-a"
        assert bundle.hops[0].destination == "mem0-b"
        assert bundle.hops[0].checks == ["record_digest"]

        report = verify_bundle(bundle)

        assert report.valid is True
        assert report.level == VerificationLevel.HASH_ONLY
        assert report.record_count == 3
        assert report.failures == []
        # every record digest plus the bundle digest were checked
        assert any(c.startswith("records[") for c in report.checks_performed)
        assert "bundle.digest" in report.checks_performed

    def test_verify_accepts_plain_dict(self):
        bundle = build_bundle(_records(), source="mem0-a")
        report = verify_bundle(bundle.model_dump(mode="json"))
        assert report.valid is True
        assert report.level == VerificationLevel.HASH_ONLY

    def test_hash_only_is_integrity_not_correctness(self):
        """The best level this verifier reaches is hash_only — never a
        correctness claim, and never a level it did not reach."""
        bundle = build_bundle(_records(), source="mem0-a")
        report = verify_bundle(bundle)
        assert report.level == VerificationLevel.HASH_ONLY
        assert report.level != VerificationLevel.RE_EXECUTED
        assert report.level != VerificationLevel.SEMANTICALLY_VALIDATED


class TestTampering:
    def _valid_dict(self):
        return build_bundle(_records(), source="mem0-a").model_dump(mode="json")

    def test_tampered_content_fails(self):
        bundle = self._valid_dict()
        bundle["records"][1]["content"] = "Avoid rm -rf / in cleanup scripts. (edited)"

        report = verify_bundle(bundle)

        assert report.valid is False
        assert report.level == VerificationLevel.UNVERIFIED
        assert any("records[1].digest:mismatch" in f for f in report.failures)

    def test_tampered_metadata_fails(self):
        bundle = self._valid_dict()
        bundle["records"][0]["metadata"]["user_id"] = "attacker"

        report = verify_bundle(bundle)

        assert report.valid is False
        assert any("records[0].digest:mismatch" in f for f in report.failures)

    def test_missing_record_digest_is_failure_not_pass(self):
        bundle = self._valid_dict()
        del bundle["records"][2]["digest"]

        report = verify_bundle(bundle)

        assert report.valid is False
        assert "records[2].digest:missing" in report.failures

    def test_missing_bundle_digest_is_failure(self):
        bundle = self._valid_dict()
        del bundle["digest"]

        report = verify_bundle(bundle)

        assert report.valid is False
        assert "bundle.digest:missing" in report.failures

    def test_missing_evidence_outcome_is_failure_not_pass(self):
        """Absence of a field is never treated as success — a bundle that
        silently dropped its outcome vocabulary fails schema parse."""
        bundle = self._valid_dict()
        del bundle["records"][0]["evidence"][0]["outcome"]

        report = verify_bundle(bundle)

        assert report.valid is False
        assert report.level == VerificationLevel.UNVERIFIED
        assert any(f.startswith("schema_parse:") for f in report.failures)

    def test_empty_bundle_fails(self):
        bundle = build_bundle([], source="mem0-a")
        report = verify_bundle(bundle)
        assert report.valid is False
        assert "no_records" in report.failures


class TestCanonicalization:
    def test_record_digests_are_deterministic(self):
        """Record digests depend only on record content — not on when the
        bundle was built — so two exports of the same records agree per-record
        even though bundle created_at differs."""
        a = build_bundle(_records(), source="mem0-a")
        b = build_bundle(_records(), source="mem0-a")
        assert [r.digest for r in a.records] == [r.digest for r in b.records]

    def test_bundle_survives_json_round_trip(self):
        """Digests are computed over canonical JSON, so a bundle that
        round-trips through text still verifies."""
        import json

        bundle = build_bundle(_records(), source="mem0-a")
        text = json.dumps(bundle.model_dump(mode="json"))
        report = verify_bundle(json.loads(text))
        assert report.valid is True
        assert report.level == VerificationLevel.HASH_ONLY

    def test_dict_insertion_order_does_not_change_digest(self):
        records = _records()
        bundle = build_bundle(records, source="mem0-a")

        reordered = {
            "evidence": records[0]["evidence"],
            "metadata": records[0]["metadata"],
            "content": records[0]["content"],
            "memory_id": records[0]["memory_id"],
        }
        assert compute_digest(reordered) == bundle.records[0].digest

    def test_canonical_json_is_deterministic(self):
        assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


class TestMemoryBundleMethods:
    """export_bundle / import_bundle wiring against a (mocked) Memory client."""

    @pytest.fixture
    def memory(self, mocker):
        mock_embedder = mocker.MagicMock()
        mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

        mock_vector_store = mocker.MagicMock()
        mock_vector_store.return_value.search.return_value = []
        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
        )

        mock_llm = mocker.MagicMock()
        mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

        from mem0.memory.main import Memory

        instance = Memory()
        instance.config = mocker.MagicMock()
        instance.config.custom_instructions = None
        instance.config.custom_update_memory_prompt = None
        instance.custom_instructions = None
        instance.api_version = "v1.1"
        instance.db.get_last_messages = mocker.MagicMock(return_value=[])
        instance.db.save_messages = mocker.MagicMock()
        return instance

    def _get_all_stub(self):
        return {
            "results": [
                {
                    "id": "mem-001",
                    "memory": "Use cmake for this project.",
                    "hash": "abc",
                    "created_at": "2026-09-28T00:00:00+00:00",
                    "updated_at": "2026-09-28T00:00:00+00:00",
                    "user_id": "u1",
                },
                {
                    "id": "mem-002",
                    "memory": "Avoid rm -rf / in cleanup scripts.",
                    "hash": "def",
                    "created_at": "2026-09-28T00:00:00+00:00",
                    "updated_at": "2026-09-28T00:00:00+00:00",
                    "user_id": "u1",
                    "metadata": {"source_doc": "runbook.md"},
                },
            ]
        }

    def test_export_bundle_shape(self, memory):
        memory.get_all = lambda **kwargs: self._get_all_stub()

        bundle = export_bundle(memory, user_id="u1", source="deployment-a", destination="deployment-b")

        assert bundle["format"] == BUNDLE_FORMAT
        assert bundle["source"] == "deployment-a"
        assert len(bundle["records"]) == 2
        assert bundle["records"][0]["memory_id"] == "mem-001"
        assert bundle["records"][0]["content"] == "Use cmake for this project."
        # mem0 fields ride along as metadata, not as invented evidence
        assert bundle["records"][0]["metadata"]["user_id"] == "u1"
        assert bundle["records"][1]["metadata"]["source_doc"] == "runbook.md"
        assert bundle["records"][0]["evidence"] == []
        assert len(bundle["hops"]) == 1

        # the exported bundle must verify
        report = verify_bundle(bundle)
        assert report.valid is True
        assert report.level == VerificationLevel.HASH_ONLY

    def test_export_requires_scope(self, memory):
        with pytest.raises(ValueError, match="user_id, agent_id, run_id"):
            export_bundle(memory)

    def test_import_bundle_fail_closed(self, memory):
        memory.get_all = lambda **kwargs: self._get_all_stub()
        bundle = export_bundle(memory, user_id="u1")
        bundle["records"][0]["content"] = "tampered"

        memory.add = MagicMock()
        result = import_bundle(memory, bundle, user_id="u2")

        assert result["imported"] == 0
        assert result["verification"]["valid"] is False
        assert result["verification"]["level"] == "unverified"
        assert memory.add.call_count == 0  # nothing added, no partial import

    def test_import_bundle_stamps_provenance(self, memory):
        memory.get_all = lambda **kwargs: self._get_all_stub()
        bundle = export_bundle(memory, user_id="u1")

        add_mock = MagicMock()
        memory.add = add_mock

        result = import_bundle(memory, bundle, user_id="u2")

        assert result["imported"] == 2
        assert result["verification"]["valid"] is True
        assert result["verification"]["level"] == "hash_only"

        assert add_mock.call_count == 2
        first_call = add_mock.call_args_list[0]
        assert first_call.args[0] == "Use cmake for this project."
        assert first_call.kwargs["infer"] is False  # content is not rewritten
        assert first_call.kwargs["user_id"] == "u2"
        stamped = first_call.kwargs["metadata"]["bundle_provenance"]
        assert stamped["source"] == "mem0"
        assert stamped["verification_level"] == "hash_only"
        assert stamped["imported_at"]

    def test_import_requires_scope_on_valid_bundle(self, memory):
        memory.get_all = lambda **kwargs: self._get_all_stub()
        bundle = export_bundle(memory, user_id="u1")

        with pytest.raises(ValueError, match="user_id, agent_id, run_id"):
            import_bundle(memory, bundle)
