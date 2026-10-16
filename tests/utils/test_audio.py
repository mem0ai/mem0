"""Tests for the optional FunASR audio transcription helper.

These tests fully mock the FunASR model and the Memory instance so that
CI never downloads model weights or makes any network call. They exercise
three things:

1. The helper lazy-imports ``funasr`` and raises a clear, actionable
   ``ImportError`` (with an install hint) when the package is absent.
2. Given a (mocked) FunASR result, the helper produces transcript text and
   preserves speaker turns as ``metadata``.
3. The transcript text + speaker-turn metadata are passed straight into the
   existing ``Memory.add()`` path (no new first-class API).
"""

import sys
from unittest.mock import MagicMock

import pytest


# A realistic FunASR ``AutoModel.generate()`` return value for a speaker
# diarization pipeline: a single dict whose ``sentence_info`` carries one
# entry per utterance with a ``spk`` (speaker id), ``text``, and timestamps.
FAKE_FUNASR_RESULT = [
    {
        "text": "hello there i am alice how are you i am fine thanks bob",
        "sentence_info": [
            {"text": "hello there i am alice", "spk": 0, "start": 0, "end": 1500},
            {"text": "how are you", "spk": 1, "start": 1500, "end": 2200},
            {"text": "i am fine thanks bob", "spk": 0, "start": 2200, "end": 3800},
        ],
    }
]


@pytest.fixture
def mock_funasr(monkeypatch):
    """Install a fake ``funasr`` module exposing ``AutoModel``.

    ``AutoModel(...)`` returns a model whose ``.generate(...)`` yields
    ``FAKE_FUNASR_RESULT`` so no real weights are loaded.
    """
    fake_module = MagicMock()
    fake_model = MagicMock()
    fake_model.generate.return_value = FAKE_FUNASR_RESULT
    fake_module.AutoModel.return_value = fake_model
    monkeypatch.setitem(sys.modules, "funasr", fake_module)
    return fake_module, fake_model


def test_missing_funasr_raises_actionable_import_error(monkeypatch):
    """When ``funasr`` is not installed, the helper must raise a clear hint."""
    from mem0.utils.audio import transcribe_audio_to_memory

    # Force the lazy import to fail regardless of the real environment.
    monkeypatch.setitem(sys.modules, "funasr", None)

    memory = MagicMock()
    with pytest.raises(ImportError) as exc_info:
        transcribe_audio_to_memory("/tmp/sample.wav", memory=memory, user_id="alice")

    message = str(exc_info.value)
    assert "funasr" in message.lower()
    assert "mem0ai[audio]" in message
    # The Memory path must never be reached if the dependency is missing.
    memory.add.assert_not_called()


def test_transcribe_produces_text_and_speaker_turn_metadata(mock_funasr):
    """Helper returns transcript text and structured speaker-turn metadata."""
    from mem0.utils.audio import transcribe_audio_to_memory

    memory = MagicMock()
    memory.add.return_value = {"results": []}

    result = transcribe_audio_to_memory("/tmp/sample.wav", memory=memory, user_id="alice")

    # Full transcript text is surfaced to the caller.
    assert result["transcript"] == FAKE_FUNASR_RESULT[0]["text"]

    # Speaker turns preserve order, speaker id, and per-turn text.
    turns = result["speaker_turns"]
    assert turns == [
        {"speaker": "speaker_0", "text": "hello there i am alice", "start": 0, "end": 1500},
        {"speaker": "speaker_1", "text": "how are you", "start": 1500, "end": 2200},
        {"speaker": "speaker_0", "text": "i am fine thanks bob", "start": 2200, "end": 3800},
    ]


def test_transcript_text_and_metadata_passed_to_memory_add(mock_funasr):
    """The transcript + speaker turns must flow into the existing add() path."""
    from mem0.utils.audio import transcribe_audio_to_memory

    memory = MagicMock()
    memory.add.return_value = {"results": [{"id": "1", "memory": "x", "event": "ADD"}]}

    transcribe_audio_to_memory(
        "/tmp/sample.wav",
        memory=memory,
        user_id="alice",
        metadata={"source": "meeting-2026-06-16"},
    )

    memory.add.assert_called_once()
    call = memory.add.call_args

    # Positional transcript text passed as the messages argument.
    assert call.args[0] == FAKE_FUNASR_RESULT[0]["text"]

    # Session identifier forwarded unchanged.
    assert call.kwargs["user_id"] == "alice"

    # Speaker turns recorded under metadata; caller metadata is merged, not lost.
    metadata = call.kwargs["metadata"]
    assert metadata["source"] == "meeting-2026-06-16"
    assert metadata["audio_source"] == "/tmp/sample.wav"
    assert metadata["speaker_turns"] == [
        {"speaker": "speaker_0", "text": "hello there i am alice", "start": 0, "end": 1500},
        {"speaker": "speaker_1", "text": "how are you", "start": 1500, "end": 2200},
        {"speaker": "speaker_0", "text": "i am fine thanks bob", "start": 2200, "end": 3800},
    ]


def test_funasr_model_constructed_and_generate_called(mock_funasr):
    """AutoModel is constructed via the lazy import and generate() is invoked."""
    fake_module, fake_model = mock_funasr
    from mem0.utils.audio import transcribe_audio_to_memory

    memory = MagicMock()
    memory.add.return_value = {"results": []}

    transcribe_audio_to_memory("/tmp/sample.wav", memory=memory, user_id="alice")

    fake_module.AutoModel.assert_called_once()
    fake_model.generate.assert_called_once()
    # The audio path is forwarded to FunASR's generate() input.
    assert fake_model.generate.call_args.kwargs.get("input") == "/tmp/sample.wav"
