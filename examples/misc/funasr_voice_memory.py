"""
Store voice memories with a local FunASR transcription server.

This example keeps FunASR out of the core mem0 dependency graph. Run FunASR as
an OpenAI-compatible local transcription endpoint, then store the transcript via
the existing MemoryClient.add() API.

Setup:

    pip install mem0ai openai
    pip install "funasr>=1.3.22"
    funasr-server --model sensevoice --device cuda --host 127.0.0.1 --port 8000

Usage:

    export MEM0_API_KEY="your_mem0_api_key"
    python examples/misc/funasr_voice_memory.py ./meeting.wav --user-id alex
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mem0 import MemoryClient

DEFAULT_FUNASR_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_FUNASR_MODEL = "iic/SenseVoiceSmall"


def transcribe_with_funasr(
    audio_path: str | Path,
    *,
    base_url: str = DEFAULT_FUNASR_BASE_URL,
    model: str = DEFAULT_FUNASR_MODEL,
) -> Any:
    """Transcribe an audio file through FunASR's OpenAI-compatible endpoint."""

    from openai import OpenAI

    client = OpenAI(api_key="EMPTY", base_url=base_url)
    with Path(audio_path).open("rb") as audio_file:
        return client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            response_format="verbose_json",
        )


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def transcript_to_memory_messages(
    text: str,
    *,
    segments: list[Any] | None = None,
) -> list[dict[str, str]]:
    """Convert a transcript into messages accepted by MemoryClient.add()."""

    messages: list[dict[str, str]] = []
    for segment in segments or []:
        segment_text = str(_field(segment, "text", "") or "").strip()
        if not segment_text:
            continue
        speaker = str(_field(segment, "speaker", "") or "").strip()
        content = f"[{speaker}] {segment_text}" if speaker else segment_text
        messages.append({"role": "user", "content": content})

    if messages:
        return messages

    clean_text = text.strip()
    if not clean_text:
        return []
    return [{"role": "user", "content": clean_text}]


def build_memory_metadata(
    *,
    audio_path: str | Path,
    model: str = DEFAULT_FUNASR_MODEL,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata that keeps the original audio source traceable."""

    metadata: dict[str, Any] = {
        "source": "funasr",
        "audio_path": str(audio_path),
        "stt_model": model,
    }
    metadata.update(extra or {})
    return metadata


def remember_audio_file(
    audio_path: str | Path,
    *,
    user_id: str,
    memory_client: "MemoryClient | None" = None,
    base_url: str = DEFAULT_FUNASR_BASE_URL,
    model: str = DEFAULT_FUNASR_MODEL,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Transcribe an audio file and store the transcript as mem0 memories."""

    transcript = transcribe_with_funasr(audio_path, base_url=base_url, model=model)
    text = str(_field(transcript, "text", "") or "").strip()
    segments = _field(transcript, "segments", None)
    messages = transcript_to_memory_messages(text, segments=segments)
    if not messages:
        raise ValueError("FunASR returned an empty transcript.")

    if memory_client is None:
        from mem0 import MemoryClient

        memory_client = MemoryClient()
    client = memory_client
    return client.add(
        messages,
        user_id=user_id,
        metadata=build_memory_metadata(audio_path=audio_path, model=model, extra=metadata),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Store a FunASR transcript as mem0 memory.")
    parser.add_argument("audio_path", help="Path to the audio file to remember.")
    parser.add_argument("--user-id", required=True, help="mem0 user_id for the memory.")
    parser.add_argument("--base-url", default=DEFAULT_FUNASR_BASE_URL, help="FunASR OpenAI-compatible base URL.")
    parser.add_argument("--model", default=DEFAULT_FUNASR_MODEL, help="FunASR model name.")
    args = parser.parse_args()

    result = remember_audio_file(
        args.audio_path,
        user_id=args.user_id,
        base_url=args.base_url,
        model=args.model,
    )
    print(result)


if __name__ == "__main__":
    main()
