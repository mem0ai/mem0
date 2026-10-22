"""Optional FunASR audio transcription helper.

This module turns an audio file into a transcript and feeds that transcript
into the *existing* :meth:`mem0.Memory.add` path. Speaker turns (who said what)
are preserved as ``metadata`` rather than as a new first-class ingestion API.

``funasr`` (and its ``torch`` backend) is an **optional** dependency. It is
imported lazily inside :func:`transcribe_audio_to_memory` so that importing
``mem0`` never requires the audio stack. If the dependency is missing, a clear
``ImportError`` with an install hint is raised.

Install the optional extra with::

    pip install "mem0ai[audio]"

Example::

    from mem0 import Memory
    from mem0.utils.audio import transcribe_audio_to_memory

    memory = Memory()
    transcribe_audio_to_memory("meeting.wav", memory=memory, user_id="alice")
"""

from typing import Any, Dict, List, Optional

# Default FunASR pipeline. ``paraformer-zh`` handles ASR while the ``cam++``
# speaker model + VAD/punctuation models enable speaker-segmented output via
# the ``sentence_info`` field returned by ``AutoModel.generate``.
DEFAULT_FUNASR_MODEL = "paraformer-zh"
DEFAULT_VAD_MODEL = "fsmn-vad"
DEFAULT_PUNC_MODEL = "ct-punc"
DEFAULT_SPK_MODEL = "cam++"


def _load_funasr_model(
    model: str,
    vad_model: Optional[str],
    punc_model: Optional[str],
    spk_model: Optional[str],
    model_kwargs: Optional[Dict[str, Any]],
):
    """Lazily import FunASR and build an ``AutoModel`` for transcription.

    Args:
        model: Name/path of the ASR model.
        vad_model: Optional voice-activity-detection model name.
        punc_model: Optional punctuation-restoration model name.
        spk_model: Optional speaker-diarization model name (enables turns).
        model_kwargs: Extra keyword arguments forwarded to ``AutoModel``.

    Returns:
        An instantiated FunASR ``AutoModel``.

    Raises:
        ImportError: If the optional ``funasr`` dependency is not installed.
    """
    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise ImportError(
            "The 'funasr' library is required for audio transcription but is not "
            "installed. Install the optional audio extra with: "
            'pip install "mem0ai[audio]"'
        ) from exc

    build_kwargs: Dict[str, Any] = {"model": model}
    if vad_model:
        build_kwargs["vad_model"] = vad_model
    if punc_model:
        build_kwargs["punc_model"] = punc_model
    if spk_model:
        build_kwargs["spk_model"] = spk_model
    if model_kwargs:
        build_kwargs.update(model_kwargs)

    return AutoModel(**build_kwargs)


def _extract_speaker_turns(funasr_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a FunASR result into ordered speaker turns.

    FunASR's speaker pipeline returns a list whose first element carries a
    ``sentence_info`` list, one entry per utterance with a ``spk`` (integer
    speaker id), ``text``, and ``start``/``end`` timestamps (milliseconds).

    Args:
        funasr_result: The raw value returned by ``AutoModel.generate``.

    Returns:
        A list of ``{"speaker", "text", "start", "end"}`` dicts in spoken
        order. Empty if the result carries no per-sentence speaker info.
    """
    if not funasr_result:
        return []

    first = funasr_result[0]
    sentence_info = first.get("sentence_info") or []

    turns: List[Dict[str, Any]] = []
    for sentence in sentence_info:
        # Speaker id may be absent for single-speaker audio; normalise to a
        # stable, human-readable label so it round-trips cleanly in metadata.
        speaker_id = sentence.get("spk", 0)
        turns.append(
            {
                "speaker": f"speaker_{speaker_id}",
                "text": sentence.get("text", ""),
                "start": sentence.get("start"),
                "end": sentence.get("end"),
            }
        )
    return turns


def _extract_transcript(funasr_result: List[Dict[str, Any]], speaker_turns: List[Dict[str, Any]]) -> str:
    """Derive the full transcript text from a FunASR result.

    Prefers the top-level ``text`` field; falls back to joining the per-turn
    texts so a transcript is still produced when only ``sentence_info`` exists.

    Args:
        funasr_result: The raw value returned by ``AutoModel.generate``.
        speaker_turns: The parsed speaker turns (used as a fallback source).

    Returns:
        The transcript as a single string (possibly empty).
    """
    if funasr_result and funasr_result[0].get("text"):
        return funasr_result[0]["text"]
    return " ".join(turn["text"] for turn in speaker_turns if turn["text"]).strip()


def transcribe_audio_to_memory(
    audio: str,
    *,
    memory: Any,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_FUNASR_MODEL,
    vad_model: Optional[str] = DEFAULT_VAD_MODEL,
    punc_model: Optional[str] = DEFAULT_PUNC_MODEL,
    spk_model: Optional[str] = DEFAULT_SPK_MODEL,
    model_kwargs: Optional[Dict[str, Any]] = None,
    generate_kwargs: Optional[Dict[str, Any]] = None,
    infer: bool = True,
) -> Dict[str, Any]:
    """Transcribe an audio input with FunASR and store it via ``Memory.add``.

    The transcript text is fed into the existing :meth:`Memory.add` path. Speaker
    turns and the audio source are attached as ``metadata`` so retrieval can
    reason about who said what without introducing a new ingestion API.

    Args:
        audio: Path to an audio file (or any input FunASR's ``generate``
            accepts, e.g. raw bytes or a URL).
        memory: A synchronous ``mem0.Memory`` instance whose ``add`` method
            receives the transcript. Injected by the caller so this helper
            stays decoupled from Memory construction. ``AsyncMemory`` is not
            supported — its ``add`` is a coroutine and cannot be awaited here.
        user_id: Optional session identifier forwarded to ``Memory.add``.
        agent_id: Optional session identifier forwarded to ``Memory.add``.
        run_id: Optional session identifier forwarded to ``Memory.add``.
        metadata: Optional caller metadata merged into the result metadata.
            ``audio_source`` and ``speaker_turns`` are reserved keys — they are
            always set by this function and will overwrite any caller-supplied
            values with the same name.
        model: FunASR ASR model name/path.
        vad_model: Optional voice-activity-detection model name.
        punc_model: Optional punctuation-restoration model name.
        spk_model: Optional speaker-diarization model name; enables speaker
            turns. Pass ``None`` to disable diarization.
        model_kwargs: Extra keyword arguments forwarded to ``AutoModel``.
        generate_kwargs: Extra keyword arguments forwarded to ``model.generate``.
        infer: Forwarded to ``Memory.add``; controls LLM-based memory extraction.

    Returns:
        A dict with ``transcript`` (str), ``speaker_turns`` (list) and
        ``memory_result`` (the value returned by ``Memory.add``).

    Raises:
        ImportError: If the optional ``funasr`` dependency is not installed.
        ValueError: If FunASR returns an empty transcript.

    Note:
        Each call to this function constructs a new ``AutoModel`` instance,
        which loads model weights from disk. ``model_kwargs`` is forwarded as
        constructor arguments to ``AutoModel`` and cannot inject an
        already-instantiated model, so reusing a model across calls would
        require a future signature change (e.g. accepting a pre-built
        ``AutoModel``).
    """
    funasr_model = _load_funasr_model(model, vad_model, punc_model, spk_model, model_kwargs)

    generate_args: Dict[str, Any] = {"input": audio}
    if generate_kwargs:
        generate_args.update(generate_kwargs)
    funasr_result = funasr_model.generate(**generate_args)

    speaker_turns = _extract_speaker_turns(funasr_result)
    transcript = _extract_transcript(funasr_result, speaker_turns)

    if not transcript.strip():
        raise ValueError("FunASR produced an empty transcript for the given audio input; nothing was stored in memory.")

    # Reserved metadata keys carry the structured audio context. Caller metadata
    # is layered first so explicit reserved keys here remain authoritative.
    combined_metadata: Dict[str, Any] = dict(metadata or {})
    combined_metadata["audio_source"] = audio
    combined_metadata["speaker_turns"] = speaker_turns

    memory_result = memory.add(
        transcript,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        metadata=combined_metadata,
        infer=infer,
    )

    return {
        "transcript": transcript,
        "speaker_turns": speaker_turns,
        "memory_result": memory_result,
    }
