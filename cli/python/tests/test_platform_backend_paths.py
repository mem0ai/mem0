from unittest.mock import MagicMock

from mem0_cli.backend.platform import PlatformBackend


def _backend(sample_config):
    backend = PlatformBackend(sample_config.platform)
    backend._client = MagicMock()
    backend._client.request.return_value = MagicMock(
        status_code=200,
        json=lambda: {"message": "ok"},
        headers={},
        raise_for_status=lambda: None,
    )
    return backend


def test_memory_id_path_segments_are_encoded(sample_config):
    backend = _backend(sample_config)

    backend.get("mem/a?b#c")
    backend.update("mem/a?b#c", content="updated")
    backend.delete("mem/a?b#c")

    paths = [call.args[1] for call in backend._client.request.call_args_list]
    assert paths == [
        "/v1/memories/mem%2Fa%3Fb%23c/",
        "/v1/memories/mem%2Fa%3Fb%23c/",
        "/v1/memories/mem%2Fa%3Fb%23c/",
    ]


def test_entity_and_event_path_segments_are_encoded(sample_config):
    backend = _backend(sample_config)

    backend.delete_entities(user_id="org/team?active#frag")
    backend.get_event("evt/a?b#c")

    paths = [call.args[1] for call in backend._client.request.call_args_list]
    assert paths == [
        "/v2/entities/user/org%2Fteam%3Factive%23frag/",
        "/v1/event/evt%2Fa%3Fb%23c/",
    ]
