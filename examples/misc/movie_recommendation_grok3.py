"""
Memory-Powered Movie Recommendation Assistant (Grok 3 + Mem0)
This script builds a personalized movie recommender that remembers your preferences
(e.g. dislikes horror, loves romcoms) using Mem0 as a memory layer and Grok 3 for responses.

In order to run this file, you need to set up your Mem0 API at Mem0 platform and also need an XAI API key.
export XAI_API_KEY="your_xai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
"""

import os

from openai import OpenAI

from mem0 import Memory

# Configure Mem0 with Grok 3 and Qdrant
config = {
    "vector_store": {"provider": "qdrant", "config": {"embedding_model_dims": 384}},
    "llm": {
        "provider": "xai",
        "config": {
            "model": "grok-3-beta",
            "temperature": 0.1,
            "max_tokens": 2000,
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "all-MiniLM-L6-v2"  # open embedding model
        },
    },
}

# Instantiate memory layer
memory = Memory.from_config(config)

# Initialize Grok 3 client
grok_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)


def recommend_movie_with_memory(user_id: str, user_query: str):
    # Retrieve prior memory about movies
    past_memories = memory.search("movie preferences", user_id=user_id)

    prompt = user_query
    if past_memories:
        prompt += f"\nPreviously, the user mentioned: {past_memories}"

    # Generate movie recommendation using Grok 3
    response = grok_client.chat.completions.create(model="grok-3-beta", messages=[{"role": "user", "content": prompt}])
    recommendation = response.choices[0].message.content

    # Store conversation in memory
    memory.add(
        [{"role": "user", "content": user_query}, {"role": "assistant", "content": recommendation}],
        user_id=user_id,
        metadata={"category": "movie"},
    )

    return recommendation


# Example Usage
if __name__ == "__main__":
    user_id = "arshi"
    recommend_movie_with_memory(user_id, "I'm looking for a movie to watch tonight. Any suggestions?")
    # OUTPUT: You have watched Intersteller last weekend and you don't like horror movies, maybe you can watch "Purple Hearts" today.
    recommend_movie_with_memory(
        user_id, "Can we skip the tearjerkers? I really enjoyed Notting Hill and Crazy Rich Asians."
    )
    # OUTPUT: Got it — no sad endings! You might enjoy "The Proposal" or "Love, Rosie". They’re both light-hearted romcoms with happy vibes.
    recommend_movie_with_memory(user_id, "Any light-hearted movie I can watch after work today?")
    # OUTPUT: Since you liked Crazy Rich Asians and The Proposal, how about "The Intern" or "Isn’t It Romantic"? Both are upbeat, funny, and perfect for relaxing.
    recommend_movie_with_memory(user_id, "I’ve already watched The Intern. Something new maybe?")
    # OUTPUT: No problem! Try "Your Place or Mine" - romcoms that match your taste and are tear-free!
