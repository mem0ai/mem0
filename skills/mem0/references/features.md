# Platform Features -- Mem0 Platform

Additional platform capabilities beyond core CRUD operations.

## Table of Contents
- [Custom Categories](#custom-categories)
- [Custom Instructions (Selective Memory)](#custom-instructions)
- [Webhooks](#webhooks)
- [Multimodal Support](#multimodal-support)
- [Async Client](#async-client)

## Custom Categories

Replace Mem0's default 15 labels with domain-specific categories. The system automatically tags memories to the closest matching category.

### Default Categories (15)
`personal_details`, `family`, `professional_details`, `sports`, `travel`, `food`, `music`, `health`, `technology`, `hobbies`, `fashion`, `entertainment`, `milestones`, `user_preferences`, `misc`

### Configuration

**Set project-level categories:**
```python
new_categories = [
    {"lifestyle_management": "Tracks daily routines, habits, wellness activities"},
    {"seeking_structure": "Documents goals around creating routines and systems"},
    {"personal_information": "Basic information about the user"}
]
client.project.update(custom_categories=new_categories)
```
```javascript
await client.project.update({ custom_categories: new_categories });
```

**Retrieve active categories:**
```python
categories = client.project.get(fields=["custom_categories"])
```

### Key Constraint
Per-request overrides (`custom_categories=...` on `client.add`) are **not supported** on the managed API. Only project-level configuration works. Workaround: store ad-hoc labels in `metadata` field.

### Memory Object with Categories
Memories include a `categories` array and `structured_attributes` object with temporal metadata: `day`, `hour`, `year`, `month`, `minute`, `quarter`, `is_weekend`, `day_of_week`, `day_of_year`, `week_of_year`.

---

## Custom Instructions

Natural language filters that control what information Mem0 extracts when creating memories.

### Set Instructions
```python
client.project.update(custom_instructions="Your guidelines here...")
```
```javascript
await client.project.update({ custom_instructions: "Your guidelines here..." });
```

### Retrieve Instructions
```python
response = client.project.get(fields=["custom_instructions"])
```

### Template Structure
1. **Task Description** -- brief extraction overview
2. **Information Categories** -- numbered sections with specific details to capture
3. **Processing Guidelines** -- quality and handling rules
4. **Exclusion List** -- sensitive/irrelevant data to filter out

### Domain Examples

**E-commerce:** Capture product issues, preferences, service experience; exclude payment data.

**Education:** Extract learning progress, student preferences, performance patterns; exclude specific grades.

**Finance:** Track financial goals, life events, investment interests; exclude account numbers and SSNs.

### Best Practices
- Start simply, test with sample messages, iterate based on results
- Avoid overly lengthy instructions
- Be specific about what to include AND exclude

---

## Webhooks

Real-time event notifications for memory operations.

### Supported Events
| Event | Trigger |
|-------|---------|
| `memory_add` | Memory created |
| `memory_update` | Memory modified |
| `memory_delete` | Memory removed |
| `memory_categorize` | Memory tagged |

### Create Webhook
```python
webhook = client.create_webhook(
    url="https://your-app.com/webhook",
    name="Memory Logger",
    project_id="proj_123",
    event_types=["memory_add", "memory_categorize"]
)
```

### Manage Webhooks
```python
# Retrieve
webhooks = client.get_webhooks(project_id="proj_123")

# Update
client.update_webhook(
    name="Updated Logger",
    url="https://your-app.com/new-webhook",
    event_types=["memory_update", "memory_add"],
    webhook_id="wh_123"
)

# Delete
client.delete_webhook(webhook_id="wh_123")
```

### Payload Structure
Memory events contain: ID, data object with memory content, event type (`ADD`/`UPDATE`/`DELETE`).
Categorization events contain: memory ID, event type (`CATEGORIZE`), assigned category labels.

---

## Multimodal Support

Mem0 can process images and documents alongside text.

### Supported Media Types
- Images: JPG, PNG
- Documents: MDX, TXT, PDF

### Image via URL
```python
image_message = {
    "role": "user",
    "content": {
        "type": "image_url",
        "image_url": {"url": "https://example.com/image.jpg"}
    }
}
client.add([image_message], user_id="alice")
```

### Image via Base64
```python
import base64
with open("photo.jpg", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode("utf-8")

image_message = {
    "role": "user",
    "content": {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
    }
}
client.add([image_message], user_id="alice")
```

### Document (MDX/TXT)
```python
doc_message = {
    "role": "user",
    "content": {"type": "mdx_url", "mdx_url": {"url": document_url}}
}
client.add([doc_message], user_id="alice")
```

### PDF Document
```python
pdf_message = {
    "role": "user",
    "content": {"type": "pdf_url", "pdf_url": {"url": pdf_url}}
}
client.add([pdf_message], user_id="alice")
```

---

## Async Client

Non-blocking operations for high-throughput applications.

### Python
```python
from mem0 import AsyncMemoryClient
client = AsyncMemoryClient(api_key="your-api-key")

await client.add(messages, user_id="alice")
results = await client.search("query", user_id="alice")
memories = await client.get_all(filters={"AND": [{"user_id": "alice"}]})
await client.delete(memory_id="...")
await client.delete_all(user_id="alice")
history = await client.history(memory_id="...")
```

### JavaScript
The JavaScript SDK is async by default -- all methods return promises:
```javascript
const client = new MemoryClient({ apiKey: 'your-api-key' });
await client.add(messages, { user_id: "alice" });
```
