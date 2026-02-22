# Interest Extraction for Personalized Feeds

## Problem

You want to build a personalized social media/YouTube feed based on user interests, but:
- Querying graph at read-time is slow for feed ranking
- Need fast access to user interests for real-time recommendations
- Want to track interest intensity and evolution

## Solution: Hybrid Approach

### Write-Time: Extract Interests with Custom Prompts
Extract and store interests during memory creation for fast retrieval.

### Read-Time: Enrich with Graph Relationships
Use graph to find related topics and deeper context.

---

## Implementation

### Step 1: Add Interest Extraction Prompt

Create a custom prompt that extracts interests during storage:

```python
# In api/seed_prompts.py or via UI

INTEREST_EXTRACTION_PROMPT = """
You are analyzing user messages to extract their interests and preferences for content recommendations.

Extract the following from the user's message:

1. **Primary Interests**: Main topics they care about (technology, cooking, sports, etc.)
2. **Content Types**: Preferred content formats (videos, articles, tutorials, etc.)
3. **Specific Topics**: Detailed interests (Python programming, Italian cooking, soccer, etc.)
4. **Sentiment**: How they feel about each topic (loves, likes, dislikes, curious about)
5. **Intensity**: How strong their interest is (casual, moderate, passionate)

Format as structured metadata:
{
  "interests": {
    "primary": ["technology", "cooking"],
    "specific": ["Python programming", "Italian recipes", "AI/ML"],
    "content_types": ["tutorial videos", "technical articles"],
    "sentiment": {
      "Python programming": "passionate",
      "Italian recipes": "curious"
    },
    "intensity": {
      "Python programming": "high",
      "Italian recipes": "moderate"
    }
  }
}

User message: {text}

Extract interests as structured JSON.
"""
```

### Step 2: Store Interests in Metadata

When creating memories, interests are automatically extracted:

```python
# Example: User says "I've been learning Python lately, love building AI apps"

# mem0 processes with custom prompt and stores:
{
  "id": "mem_123",
  "memory": "User is learning Python and enjoys building AI applications",
  "metadata_": {
    "interests": {
      "primary": ["technology", "programming"],
      "specific": ["Python", "AI/ML", "app development"],
      "content_types": ["tutorials", "documentation", "projects"],
      "sentiment": {
        "Python": "passionate",
        "AI/ML": "passionate"
      },
      "intensity": {
        "Python": "high",
        "AI/ML": "high"
      }
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Step 3: Fast Interest Queries

Query interests directly from metadata for feed building:

```python
import requests
from collections import Counter
from datetime import datetime, timedelta

def get_user_interests(user_id: str, days_recent: int = 30):
    """
    Get user interests for feed personalization

    Returns:
        {
            "interests": ["Python", "AI/ML", "cooking"],
            "intensity": {"Python": "high", "AI/ML": "high"},
            "trending": ["AI/ML"],  # interests mentioned more recently
            "content_types": ["tutorial videos", "articles"]
        }
    """
    # Query recent memories
    cutoff_date = int((datetime.now() - timedelta(days=days_recent)).timestamp())

    response = requests.post(
        "http://localhost:8765/api/v1/memories/filter",
        json={
            "user_id": user_id,
            "from_date": cutoff_date,
            "page": 1,
            "size": 100
        }
    )

    memories = response.json()["items"]

    # Aggregate interests
    all_interests = []
    interest_sentiments = {}
    interest_intensities = {}
    content_types = set()
    interest_timestamps = {}

    for memory in memories:
        metadata = memory.get("metadata_", {})
        interests = metadata.get("interests", {})
        timestamp = memory.get("created_at")

        # Collect interests
        for interest in interests.get("specific", []):
            all_interests.append(interest)

            # Track when interest was mentioned
            if interest not in interest_timestamps:
                interest_timestamps[interest] = []
            interest_timestamps[interest].append(timestamp)

        # Collect sentiment
        for topic, sentiment in interests.get("sentiment", {}).items():
            interest_sentiments[topic] = sentiment

        # Collect intensity
        for topic, intensity in interests.get("intensity", {}).items():
            interest_intensities[topic] = intensity

        # Collect content types
        content_types.update(interests.get("content_types", []))

    # Count frequency
    interest_counts = Counter(all_interests)
    top_interests = [interest for interest, _ in interest_counts.most_common(10)]

    # Calculate trending (mentioned more in recent half vs older half)
    mid_point = cutoff_date + ((int(datetime.now().timestamp()) - cutoff_date) / 2)
    trending = []

    for interest, timestamps in interest_timestamps.items():
        recent_mentions = sum(1 for ts in timestamps if ts > mid_point)
        older_mentions = sum(1 for ts in timestamps if ts <= mid_point)

        if recent_mentions > older_mentions * 1.5:  # 50% more mentions recently
            trending.append(interest)

    return {
        "interests": top_interests,
        "sentiment": interest_sentiments,
        "intensity": interest_intensities,
        "trending": trending,
        "content_types": list(content_types),
        "interest_counts": dict(interest_counts)
    }


# Usage
interests = get_user_interests("user123", days_recent=30)
print(f"Top interests: {interests['interests']}")
print(f"Trending: {interests['trending']}")
print(f"Content types: {interests['content_types']}")
```

### Step 4: Build Feed Rankings

Use extracted interests to rank feed items:

```python
def rank_feed_items(user_interests: dict, feed_items: list) -> list:
    """
    Rank feed items based on user interests

    Args:
        user_interests: Output from get_user_interests()
        feed_items: List of content items with topics/tags

    Returns:
        Ranked list of feed items with scores
    """
    scored_items = []

    for item in feed_items:
        score = 0
        matched_interests = []

        # Match item topics with user interests
        item_topics = set(item.get("topics", []))
        user_interest_set = set(user_interests["interests"])

        # Base score: topic match
        matches = item_topics & user_interest_set
        score += len(matches) * 10
        matched_interests.extend(matches)

        # Bonus: high intensity interests
        for interest in matches:
            intensity = user_interests["intensity"].get(interest)
            if intensity == "high":
                score += 15
            elif intensity == "moderate":
                score += 5

        # Bonus: positive sentiment
        for interest in matches:
            sentiment = user_interests["sentiment"].get(interest)
            if sentiment == "passionate":
                score += 20
            elif sentiment == "likes":
                score += 10

        # Bonus: trending topics
        trending_matches = item_topics & set(user_interests["trending"])
        score += len(trending_matches) * 25  # Big boost for trending

        # Bonus: preferred content type
        if item.get("content_type") in user_interests["content_types"]:
            score += 10

        scored_items.append({
            **item,
            "score": score,
            "matched_interests": matched_interests,
            "is_trending": bool(trending_matches)
        })

    # Sort by score
    scored_items.sort(key=lambda x: x["score"], reverse=True)

    return scored_items


# Example feed items
feed_items = [
    {
        "id": "video_1",
        "title": "Python AI Tutorial: Build a Chatbot",
        "topics": ["Python", "AI/ML", "tutorials"],
        "content_type": "tutorial video"
    },
    {
        "id": "video_2",
        "title": "Italian Pasta Recipes",
        "topics": ["cooking", "Italian recipes"],
        "content_type": "recipe video"
    },
    {
        "id": "article_1",
        "title": "Advanced Python Patterns",
        "topics": ["Python", "software engineering"],
        "content_type": "article"
    }
]

interests = get_user_interests("user123")
ranked_feed = rank_feed_items(interests, feed_items)

for item in ranked_feed:
    print(f"{item['title']}: {item['score']} points")
    print(f"  Matched: {item['matched_interests']}")
    print(f"  Trending: {item['is_trending']}")
    print()
```

---

## Step 5: Enhance with Graph Enrichment (Optional)

For **deeper personalization**, use graph enrichment to find related topics:

```python
def get_related_interests(user_id: str, primary_interest: str):
    """
    Use graph to find related topics and implicit interests

    Example: User likes "Python" -> Find they also interact with
    "FastAPI", "Django", "data science" through relationships
    """
    response = requests.get(
        f"http://localhost:8765/api/v1/memories/entity/{primary_interest}",
        params={"user_id": user_id}
    )

    entity_context = response.json()

    # Extract related entities from relationships
    related = []
    for rel in entity_context.get("relationships", []):
        if rel["relation"] in ["RELATED_TO", "USES", "INTERESTED_IN"]:
            related.append(rel["related_entity"])

    return related


# Expand user interests with graph relationships
def expand_interests_with_graph(user_interests: dict, user_id: str):
    """
    Enhance interests with graph-discovered relationships
    """
    expanded = user_interests.copy()
    expanded["related_topics"] = {}

    for interest in user_interests["interests"][:5]:  # Top 5 interests
        related = get_related_interests(user_id, interest)
        if related:
            expanded["related_topics"][interest] = related

    return expanded


# Usage
interests = get_user_interests("user123")
expanded_interests = expand_interests_with_graph(interests, "user123")

# Now include related topics in feed ranking
# Example: User likes "Python" -> also show "FastAPI", "Django" content
```

---

## Comparison: Write-Time vs Read-Time

### Write-Time (Custom Prompt) ✅ **Recommended for Feeds**

**Pros:**
- ⚡ **Fast queries** - interests pre-computed
- 📊 **Easy aggregation** - simple metadata filtering
- 🎯 **Consistent format** - structured interest data
- 🔄 **Real-time updates** - interests extracted immediately
- 💰 **Cost-effective** - query once, use many times

**Cons:**
- 🔒 Limited to what prompt extracts
- 🔄 Need to reprocess if extraction logic changes

**Best for:**
- Feed ranking
- Real-time recommendations
- Dashboard analytics
- Quick interest queries

### Read-Time (Graph Enrichment)

**Pros:**
- 🕸️ **Rich relationships** - discover implicit interests
- 🔍 **Deep context** - multi-hop reasoning
- 🎨 **Flexible** - can query different aspects

**Cons:**
- 🐌 **Slower** - graph queries + aggregation
- 💸 **More expensive** - queries on every read
- 🧩 **Complex** - need to aggregate from many memories

**Best for:**
- Deep personalization
- Discovery ("users who like X also like Y")
- Interest evolution tracking
- Related topic suggestions

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   User Conversation                         │
│        "I've been learning Python, love AI apps"            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              POST /api/v1/memories/                         │
│         (with custom interest extraction prompt)            │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  Vector Store    │    │   Relational DB      │
│  (Qdrant)        │    │   (SQLite/Postgres)  │
│                  │    │                      │
│  Embeddings      │    │  Metadata:           │
│  for semantic    │    │  {                   │
│  search          │    │    "interests": {    │
│                  │    │      "specific": [   │
│                  │    │        "Python",     │
│                  │    │        "AI/ML"       │
│                  │    │      ],              │
│                  │    │      "intensity": {  │
│                  │    │        "Python": "high"│
│                  │    │      }               │
│                  │    │    }                 │
│                  │    │  }                   │
└──────────────────┘    └──────────────────────┘
                               │
                               │ FAST QUERY ⚡
                               ▼
                    ┌──────────────────────┐
                    │   Feed Builder       │
                    │                      │
                    │  1. Get interests    │
                    │  2. Rank content     │
                    │  3. Return feed      │
                    └──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Personalized Feed   │
                    │                      │
                    │  - Python tutorials  │
                    │  - AI/ML articles    │
                    │  - Trending tech     │
                    └──────────────────────┘

        Optional: Enhance with Graph
                    │
                    ▼
        ┌──────────────────────┐
        │   Neo4j Graph        │
        │                      │
        │   Python -[USES]->   │
        │     FastAPI          │
        │                      │
        │   Python -[USED_IN]->│
        │     AI/ML            │
        └──────────────────────┘
                    │
                    │ DEEP QUERY 🕸️
                    ▼
        Expand interests with
        related topics
```

---

## Recommended Implementation

### Phase 1: Write-Time Extraction (Start Here)

```python
# 1. Create custom interest extraction prompt in UI or database
# 2. Memories automatically extract interests during storage
# 3. Query metadata for fast feed building
```

### Phase 2: Add Graph Enhancement (Later)

```python
# 1. Use graph to discover related topics
# 2. Find implicit interests from relationships
# 3. Enhance feed with "users who like X also like Y"
```

---

## Example End-to-End Flow

```python
# User conversation
user_message = "I've been watching Python tutorials on YouTube, especially AI stuff"

# 1. Store memory (interests auto-extracted)
memory = create_memory(
    user_id="user123",
    text=user_message,
    # Custom prompt extracts: ["Python", "AI/ML", "tutorials", "YouTube"]
)

# 2. Build personalized feed
interests = get_user_interests("user123")
# Returns: {
#   "interests": ["Python", "AI/ML", "tutorials"],
#   "content_types": ["tutorial videos"],
#   "intensity": {"Python": "high", "AI/ML": "high"}
# }

# 3. Rank feed content
feed = rank_feed_items(interests, available_content)
# Returns prioritized content matching user interests

# 4. (Optional) Expand with graph
expanded = expand_interests_with_graph(interests, "user123")
# Discovers: User also interacts with "FastAPI", "data science"
```

---

## Performance Comparison

| Approach | Query Time | Best Use Case |
|----------|-----------|---------------|
| **Metadata query** | ~10ms | Feed ranking, real-time |
| **Graph enrichment** | ~100ms | Deep personalization |
| **Hybrid** | ~50ms | Best of both worlds |

---

## Conclusion

✅ **Recommended: Write-Time + Metadata Queries**
- Fast, efficient, perfect for feed building
- Store interests in metadata during memory creation
- Query metadata for real-time feed ranking

🎨 **Optional: Add Graph for Deep Personalization**
- Use when you need related topics
- Great for "discover" features
- Enhances recommendations with implicit interests

The hybrid approach gives you **speed when you need it** (feed ranking) and **depth when you want it** (discovery).
