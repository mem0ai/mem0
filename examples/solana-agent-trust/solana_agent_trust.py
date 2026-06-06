"""
Solana Agent Trust + Persistent Memory: mem0 + TWZRD Agent Intel

This example shows how to combine:
- mem0: persistent agent memory across conversations
- TWZRD Agent Intel: on-chain Solana wallet trust verification

Use case: An AI assistant that remembers which agent wallets it has already
verified, avoiding redundant MCP calls, and builds a local trust history.

Requirements:
    pip install mem0ai mcp openai

Environment variables:
    MEM0_API_KEY   - from app.mem0.ai
    OPENAI_API_KEY - from platform.openai.com
"""

import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mem0 import MemoryClient
from openai import OpenAI

MCP_URL = "https://intel.twzrd.xyz/mcp"
TRUST_THRESHOLD = 0.5

mem0_client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])
openai_client = OpenAI()


async def _call_mcp(tool: str, wallet: str) -> str:
    """Call a TWZRD MCP tool."""
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, {"wallet": wallet})
            return result.content[0].text


def score_wallet(wallet: str) -> dict:
    """Fetch trust score and preflight result from TWZRD Agent Intel."""
    score_raw = asyncio.run(_call_mcp("score_agent", wallet))
    preflight_raw = asyncio.run(_call_mcp("preflight_check", wallet))
    return {"wallet": wallet, "score": score_raw, "preflight": preflight_raw}


def get_cached_trust(wallet: str, user_id: str) -> str | None:
    """Check mem0 for a previously stored trust result for this wallet."""
    memories = mem0_client.search(f"trust check {wallet}", user_id=user_id)
    if memories:
        return memories[0]["memory"]
    return None


def store_trust_result(wallet: str, result: dict, user_id: str) -> None:
    """Persist the trust result in mem0 for future sessions."""
    summary = (
        f"Wallet {wallet}: score={result['score']}, "
        f"preflight={result['preflight']}"
    )
    mem0_client.add(summary, user_id=user_id)


def check_agent_trust(wallet: str, user_id: str = "default") -> dict:
    """
    Verify a Solana agent wallet with caching via mem0.

    1. Check mem0 for a cached result (avoids redundant MCP calls).
    2. If no cache: call TWZRD Agent Intel MCP server.
    3. Store result in mem0 for future sessions.
    4. Return trust decision.
    """
    # Check memory first
    cached = get_cached_trust(wallet, user_id)
    if cached:
        print(f"[mem0 cache hit] {cached}")
        return {"wallet": wallet, "cached": True, "result": cached}

    # Live MCP check
    result = score_wallet(wallet)
    store_trust_result(wallet, result, user_id)
    print(f"[MCP check] wallet={wallet} score={result['score']}")
    return {"wallet": wallet, "cached": False, "result": result}


def run_interactive_session(user_id: str = "demo-user"):
    """Run an interactive chat session with memory-backed trust verification."""
    history = []
    system_prompt = (
        "You are a Solana agent trust verification assistant. "
        "You have access to mem0 memory and the TWZRD Agent Intel MCP server. "
        "When users ask about a wallet, check the trust score and preflight result. "
        "Remember previously checked wallets and cite cached results when available."
    )
    print("Solana Agent Trust Assistant (type 'quit' to exit)")
    print("Try: 'Check wallet D1QkbFJKiPsymJ65RKHhF6DFB8sPMfpBaFBzuHKfJGWi'")
    print()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break

        # Load relevant memories
        past_memories = mem0_client.search(user_input, user_id=user_id)
        memory_context = "\n".join(m["memory"] for m in past_memories[:3])

        # Extract wallet if present (simple heuristic)
        words = user_input.split()
        wallet = next(
            (w for w in words if len(w) >= 32 and w.isalnum()),
            None
        )

        if wallet:
            trust_data = check_agent_trust(wallet, user_id)
            user_input += f"\n[Trust data: {trust_data}]"

        messages = [
            {"role": "system", "content": system_prompt + (f"\nRelevant memory:\n{memory_context}" if memory_context else "")},
            *history,
            {"role": "user", "content": user_input},
        ]

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini", messages=messages
        )
        reply = response.choices[0].message.content
        print(f"\nAssistant: {reply}\n")

        history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply},
        ])
        mem0_client.add(f"User asked: {user_input}. Assistant: {reply}", user_id=user_id)


if __name__ == "__main__":
    run_interactive_session()
