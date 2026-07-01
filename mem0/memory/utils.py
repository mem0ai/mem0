import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from mem0.configs.prompts import (
    AGENT_MEMORY_EXTRACTION_PROMPT,
    FACT_RETRIEVAL_PROMPT,
    MEMORY_EXTRACTION_TOOL,
    USER_MEMORY_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)


def get_fact_retrieval_messages(message, is_agent_memory=False):
    """Get fact retrieval messages based on the memory type.
    
    Args:
        message: The message content to extract facts from
        is_agent_memory: If True, use agent memory extraction prompt, else use user memory extraction prompt
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if is_agent_memory:
        return AGENT_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"
    else:
        return USER_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"


def get_fact_retrieval_messages_legacy(message):
    """Legacy function for backward compatibility."""
    return FACT_RETRIEVAL_PROMPT, f"Input:\n{message}"


def ensure_json_instruction(system_prompt, user_prompt):
    """Ensure the word 'json' appears in the prompts when using json_object response format.

    OpenAI's API requires the word 'json' to appear in the messages when
    response_format is set to {"type": "json_object"}. When users provide a
    custom_instructions that doesn't include 'json', this causes a
    400 error. This function appends a JSON format instruction to the system
    prompt if 'json' is not already present in either prompt.

    Args:
        system_prompt: The system prompt string
        user_prompt: The user prompt string

    Returns:
        tuple: (system_prompt, user_prompt) with JSON instruction added if needed
    """
    combined = (system_prompt + user_prompt).lower()
    if "json" not in combined:
        system_prompt += (
            "\n\nYou must return your response in valid JSON format "
            "with a 'facts' key containing an array of strings."
        )
    return system_prompt, user_prompt


def parse_messages(messages):
    response = ""
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        # Skip messages without textual content (e.g. assistant tool-call
        # messages that carry `tool_calls` but no `content` key).
        if content is None:
            continue
        if role == "system":
            response += f"system: {content}\n"
        elif role == "user":
            response += f"user: {content}\n"
        elif role == "assistant":
            response += f"assistant: {content}\n"
    return response


def format_entities(entities):
    if not entities:
        return ""

    formatted_lines = []
    for entity in entities:
        simplified = f"{entity['source']} -- {entity['relationship']} -- {entity['destination']}"
        formatted_lines.append(simplified)

    return "\n".join(formatted_lines)

def normalize_facts(raw_facts):
    """Normalize LLM-extracted facts to a list of strings.

    Smaller LLMs (e.g. llama3.1:8b) sometimes return facts as objects
    like {"fact": "..."} or {"text": "..."} instead of plain strings.
    This mirrors the TypeScript FactRetrievalSchema validation.
    """
    if not raw_facts:
        return []
    normalized = []
    for item in raw_facts:
        if isinstance(item, str):
            fact = item
        elif isinstance(item, dict):
            fact = item.get("fact") or item.get("text")
            if fact is None:
                logger.warning("Unexpected fact shape from LLM, skipping: %s", item)
                continue
        else:
            fact = str(item)
        if fact:
            normalized.append(fact)
    return normalized


def remove_code_blocks(content: str) -> str:
    """
    Removes enclosing code block markers ```[language] and ``` from a given string.

    Remarks:
    - The function uses a regex pattern to match code blocks that may start with ``` followed by an optional language tag (letters or numbers) and end with ```.
    - If a code block is detected, it returns only the inner content, stripping out the markers.
    - If no code block markers are found, the original content is returned as-is.
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    match_res=match.group(1).strip() if match else content.strip()
    return re.sub(r"<think>.*?</think>", "", match_res, flags=re.DOTALL).strip()



def extract_json(text):
    """
    Extracts JSON content from a string, removing enclosing triple backticks and optional 'json' tag if present.
    If no code block is found, attempts to locate JSON by finding the first '{' and last '}'.
    If that also fails, returns the text as-is.
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx : end_idx + 1]
        else:
            json_str = text
    return json_str


def llm_supports_tool_calls(llm) -> bool:
    """Whether this LLM provider can recover extraction via a forced tool call.

    The recovery path (``recover_extraction_via_tools``) only works on providers
    that (a) accept ``tools`` / ``tool_choice`` and (b) return the standard
    ``{"tool_calls": [{"name", "arguments"}]}`` dict when a tool is called.
    Providers opt in explicitly by setting the class attribute
    ``supports_tool_calls = True``. This is intentionally distinct from
    AWSBedrockLLM's pre-existing ``supports_tools`` (whether the underlying
    Bedrock model family accepts tools at all): this flag specifically asserts
    "honors a forced ``tool_choice`` and returns the standard tool_calls dict",
    which is what the recovery path needs.

    The ``is True`` check is deliberate: it requires a real boolean opt-in and
    will not be tripped by the auto-populated attributes of a ``MagicMock`` in
    tests or by partially-wired providers.
    """
    return getattr(llm, "supports_tool_calls", False) is True


def parse_tool_calls_for_memory(response) -> Optional[List[Dict[str, Any]]]:
    """Pull the ``memory`` list out of a provider's tool-call response.

    Providers return ``{"content": ..., "tool_calls": [{"name", "arguments"}]}``
    (or a bare ``{"tool_calls": [...]}``) when a tool is invoked. ``arguments``
    is normally a dict but some providers hand back a JSON string. Merges the
    ``memory`` arrays across ALL tool calls (a model may answer a forced call
    with several parallel invocations, one per fact) and drops non-dict items
    (downstream reads ``m.get("text")``, so a bare string would crash the add
    pipeline). Returns the merged list (which may legitimately be empty), or
    ``None`` when no tool call carried a parseable ``memory`` list at all -
    callers use that distinction to tell "valid empty extraction" from
    "truncated/unusable tool output".
    """
    if not isinstance(response, dict):
        return None
    collected: Optional[List[Dict[str, Any]]] = None
    for call in response.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        arguments = call.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (json.JSONDecodeError, ValueError):
                continue
        if isinstance(arguments, dict):
            memory = arguments.get("memory")
            if isinstance(memory, list):
                if collected is None:
                    collected = []
                collected.extend(m for m in memory if isinstance(m, dict))
    return collected


# A forced tool call whose own structured output hits ``max_tokens`` is retried
# once at this multiple of the configured ``max_tokens``. The 4x figure comes
# from observed tool-call truncations on a real conversation corpus, where a 2x
# raise still under-shot. The absolute cap bounds the retry's cost so a large
# configured budget cannot multiply into an arbitrarily expensive call, and
# keeps the raised value inside common provider output limits.
_TOOL_RETRY_TOKEN_MULTIPLIER = 4
_TOOL_RETRY_TOKEN_CAP = 8192


def _forced_tool_extraction(llm, system_prompt, user_prompt, max_tokens=None) -> Optional[List[Dict[str, Any]]]:
    """Run one forced tool call and return its parsed memory list.

    Returns ``None`` when the call failed or produced no parseable tool call
    (see ``parse_tool_calls_for_memory``). ``max_tokens`` overrides the
    provider's configured budget for this one call (used by the truncation
    retry). Never raises.
    """
    kwargs = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # No response_format: the forced tool call supersedes it, and OpenAI
        # rejects response_format={"type": "json_object"} combined with a forced
        # tool_choice.
        "tools": [MEMORY_EXTRACTION_TOOL],
        "tool_choice": "required",
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    try:
        return parse_tool_calls_for_memory(llm.generate_response(**kwargs))
    except Exception as e:
        logger.warning("Tool-based extraction recovery failed: %s", e)
        return None


def recover_extraction_via_tools(llm, system_prompt, user_prompt) -> List[Dict[str, Any]]:
    """Recover dropped memories after a parse failure using forced tool use.

    When the extraction LLM returns prose with no JSON object, the standard
    parse path raises ``json.JSONDecodeError`` and the memories are silently
    lost. This retries the same extraction with a forced ``tool_choice`` on the
    ``save_memories`` schema: the model cannot answer a forced tool call with
    free prose, so the content-hijack that caused the drop cannot recur.

    If no tool call could be parsed at all, the forced call's own structured
    output may have been truncated (``max_tokens`` reached mid-call). In that
    case it retries once at a raised ``max_tokens`` **staying in tool mode** -
    reverting to free text would reintroduce the content-hijack the tool call
    exists to prevent. A tool call that parsed cleanly to an empty ``memory``
    list is a valid "nothing memorable" result and is returned as-is, with no
    retry spend. (Providers that drop the ``max_tokens`` override - e.g. the
    reasoning models whose params layer strips it - re-run at the same budget;
    the retry then harmlessly no-ops back to ``[]``.)

    The recovery reuses the original extraction's ``system_prompt`` and
    ``user_prompt`` (existing memories, recent messages, dates) so the
    recovered extraction sees exactly the context the failed one did - same
    fidelity, and therefore roughly the same cost as the original call. That
    cost is only paid on the rare parse-failure path, never on healthy
    extractions.

    Gated to providers that declare ``supports_tool_calls``; any failure (an
    unsupported provider, an API error, or an unparseable response) falls back
    to the current behavior by returning ``[]`` - recovery never raises.
    """
    if not llm_supports_tool_calls(llm):
        return []

    memories = _forced_tool_extraction(llm, system_prompt, user_prompt)
    if memories:
        logger.info("Recovered %d memory item(s) via forced tool call after parse failure", len(memories))
        return memories
    if memories is not None:
        # The tool call parsed cleanly to an empty list: the conversation had
        # nothing memorable. That is a valid result, not a truncation - do not
        # spend another LLM call retrying it.
        return []

    # No parseable tool call: the forced call's own output may have truncated.
    # Retry once at a raised (and capped) budget, still forcing the tool.
    current = getattr(getattr(llm, "config", None), "max_tokens", None)
    if isinstance(current, int) and current > 0:
        raised = min(current * _TOOL_RETRY_TOKEN_MULTIPLIER, _TOOL_RETRY_TOKEN_CAP)
        if raised > current:
            retried = _forced_tool_extraction(llm, system_prompt, user_prompt, max_tokens=raised)
            if retried:
                logger.info("Recovered %d memory item(s) via forced tool call after a raised-token retry", len(retried))
                return retried
    return []


def get_image_description(image_obj, llm, vision_details):
    """
    Get the description of the image
    """

    if isinstance(image_obj, str):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "A user is providing an image. Provide a high level description of the image and do not include any additional text.",
                    },
                    {"type": "image_url", "image_url": {"url": image_obj, "detail": vision_details}},
                ],
            },
        ]
    else:
        messages = [image_obj]

    response = llm.generate_response(messages=messages)
    return response


def parse_vision_messages(messages, llm=None, vision_details="auto"):
    """
    Parse the vision messages from the messages
    """
    returned_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            returned_messages.append(msg)
            continue

        # Skip messages without content (e.g. assistant tool-call messages
        # that carry `tool_calls` but no `content` key).
        if content is None:
            continue

        # Handle message content
        if isinstance(content, list):
            if llm is None:
                text_parts = [
                    part["text"] for part in msg["content"]
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                if not text_parts:
                    continue
                returned_messages.append({"role": role, "content": " ".join(text_parts)})
            else:
                description = get_image_description(msg, llm, vision_details)
                returned_messages.append({"role": role, "content": description})
        elif isinstance(content, dict) and content.get("type") == "image_url":
            if llm is None:
                continue
            image_url_obj = content.get("image_url")
            image_url = image_url_obj.get("url") if isinstance(image_url_obj, dict) else None
            if not image_url:
                raise ValueError("image_url content part is missing image_url.url")
            try:
                description = get_image_description(image_url, llm, vision_details)
                returned_messages.append({"role": role, "content": description})
            except Exception:
                raise Exception(f"Error while downloading {image_url}.")
        else:
            # Regular text content
            returned_messages.append(msg)

    return returned_messages


def process_telemetry_filters(filters):
    """
    Process the telemetry filters
    """
    if filters is None:
        return {}

    encoded_ids = {}
    if "user_id" in filters:
        encoded_ids["user_id"] = hashlib.md5(filters["user_id"].encode()).hexdigest()
    if "agent_id" in filters:
        encoded_ids["agent_id"] = hashlib.md5(filters["agent_id"].encode()).hexdigest()
    if "run_id" in filters:
        encoded_ids["run_id"] = hashlib.md5(filters["run_id"].encode()).hexdigest()

    return list(filters.keys()), encoded_ids


def sanitize_relationship_for_cypher(relationship) -> str:
    """Sanitize relationship text for Cypher queries by replacing problematic characters."""
    char_map = {
        "...": "_ellipsis_",
        "…": "_ellipsis_",
        "。": "_period_",
        "，": "_comma_",
        "；": "_semicolon_",
        "：": "_colon_",
        "！": "_exclamation_",
        "？": "_question_",
        "（": "_lparen_",
        "）": "_rparen_",
        "【": "_lbracket_",
        "】": "_rbracket_",
        "《": "_langle_",
        "》": "_rangle_",
        "'": "_apostrophe_",
        '"': "_quote_",
        "\\": "_backslash_",
        "/": "_slash_",
        "|": "_pipe_",
        "&": "_ampersand_",
        "=": "_equals_",
        "+": "_plus_",
        "*": "_asterisk_",
        "^": "_caret_",
        "%": "_percent_",
        "$": "_dollar_",
        "#": "_hash_",
        "@": "_at_",
        "!": "_bang_",
        "?": "_question_",
        "(": "_lparen_",
        ")": "_rparen_",
        "[": "_lbracket_",
        "]": "_rbracket_",
        "{": "_lbrace_",
        "}": "_rbrace_",
        "<": "_langle_",
        ">": "_rangle_",
        "-": "_",
    }

    # Apply replacements and clean up
    sanitized = relationship
    for old, new in char_map.items():
        sanitized = sanitized.replace(old, new)

    return re.sub(r"_+", "_", sanitized).strip("_")


def remove_spaces_from_entities(
    entity_list: List[Any],
    *,
    sanitize_relationship: bool = True,
) -> List[Dict[str, Any]]:
    """
    Normalize entity relation dicts from LLM/tool output: lowercase, spaces to underscores.

    Skips entries that are not non-empty dicts or that lack any of
    ``source``, ``relationship``, or ``destination`` (avoids KeyError on ``[{}]``
    or partial dicts).
    """
    required = ("source", "relationship", "destination")
    cleaned: List[Dict[str, Any]] = []
    for item in entity_list:
        if not isinstance(item, dict) or not item:
            continue
        if not all(key in item for key in required):
            continue
        item["source"] = item["source"].lower().replace(" ", "_")
        rel = item["relationship"].lower().replace(" ", "_")
        item["relationship"] = sanitize_relationship_for_cypher(rel) if sanitize_relationship else rel
        item["destination"] = item["destination"].lower().replace(" ", "_")
        cleaned.append(item)
    return cleaned

