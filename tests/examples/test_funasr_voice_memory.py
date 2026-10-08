from examples.misc.funasr_voice_memory import build_memory_metadata, transcript_to_memory_messages


def test_transcript_to_memory_messages_keeps_single_turn_text():
    messages = transcript_to_memory_messages("Remember that I prefer morning standups.")

    assert messages == [
        {
            "role": "user",
            "content": "Remember that I prefer morning standups.",
        }
    ]


def test_transcript_to_memory_messages_preserves_speaker_segments():
    messages = transcript_to_memory_messages(
        "",
        segments=[
            {"speaker": "SPEAKER_00", "text": "Alice prefers concise notes."},
            {"speaker": "SPEAKER_01", "text": "Bob owns the weekly sync."},
            {"speaker": "SPEAKER_00", "text": ""},
        ],
    )

    assert messages == [
        {"role": "user", "content": "[SPEAKER_00] Alice prefers concise notes."},
        {"role": "user", "content": "[SPEAKER_01] Bob owns the weekly sync."},
    ]


def test_build_memory_metadata_records_audio_source_and_model():
    metadata = build_memory_metadata(
        audio_path="/tmp/meeting.wav",
        model="iic/SenseVoiceSmall",
        extra={"meeting_id": "weekly"},
    )

    assert metadata == {
        "source": "funasr",
        "audio_path": "/tmp/meeting.wav",
        "stt_model": "iic/SenseVoiceSmall",
        "meeting_id": "weekly",
    }
