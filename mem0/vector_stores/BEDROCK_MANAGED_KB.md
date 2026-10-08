# Bedrock Managed Knowledge Base Support

## Overview
Adds a Mem0 vector store backend that delegates search to Amazon Bedrock Knowledge Bases instead of a local vector store.

## Usage
```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "bedrock_kb",
        "config": {
            "knowledge_base_id": "YOUR_KB_ID",
            "region": "us-east-1",
        }
    }
}
m = Memory.from_config(config)
results = m.search("What are the onboarding steps?", user_id="user1")
```

## Configuration
| Variable | Description | Default |
|---|---|---|
| KNOWLEDGE_BASE_ID | Bedrock Knowledge Base ID | None |
| AWS_REGION | AWS region for the KB | us-east-1 |
| AWS_PROFILE | AWS credentials profile | None |
| USE_AGENTIC_RETRIEVAL | Enable agentic retrieval | true |
| MAX_RESULTS | Maximum retrieval results | 5 |

## Features
- Managed search (no vector store needed)
- Agentic retrieval with query decomposition + reranking
- Automatic fallback to plain Retrieve if agentic fails
- Multi-source support (S3, Web, Confluence, SharePoint)
- Implements Mem0 VectorStoreBase interface

## SDK Requirements
- boto3 >= 1.43
- mem0ai >= 0.1

## Required IAM Permissions
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve",
    "bedrock:AgenticRetrieveStream"
  ],
  "Resource": "arn:aws:bedrock:<region>:<account-id>:knowledge-base/<kb-id>"
}
```

## References
- [Build a Managed Knowledge Base](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html)
- [Retrieve API](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve.html)
- [Agentic Retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-agentic.html)

## Direct Ingestion (CUSTOM Data Source)

When using a CUSTOM data source (created via console or API), you can ingest documents directly without S3 upload + sync:

```python
kb = BedrockKB(
    knowledge_base_id="YOUR_KB_ID",
    data_source_id="YOUR_CUSTOM_DS_ID",
    region_name="us-west-2",
    data_source_type="CUSTOM",
)

# Inline text
kb.insert(vectors=None, payloads=[{"data": "Your document content here."}])

# S3 reference (ingest a specific file without full sync)
kb.insert(vectors=None, payloads=[{"s3_uri": "s3://bucket/path/to/file.pdf"}])

# Binary file (PDF, DOCX, images, audio, video — depends on KB indexing settings)
import base64
with open("document.pdf", "rb") as f:
    encoded = base64.b64encode(f.read()).decode()
kb.insert(vectors=None, payloads=[{"data": encoded, "mime_type": "application/pdf"}])
```

### Supported mime types

- Text: `text/plain`, `text/html`, `text/csv`
- Documents: `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- With advanced indexing enabled: images (`image/png`, `image/jpeg`), audio (`audio/mp3`, `audio/wav`), video (`video/mp4`)

### Configuration

| Parameter | Description | Default |
|---|---|---|
| `data_source_type` | `"S3"` (upload + sync) or `"CUSTOM"` (direct ingestion) | `"S3"` |
| `data_source_id` | Required for both modes | Env: `BEDROCK_DATA_SOURCE_ID` |
| `data_source_bucket` | Required only for `"S3"` mode | Env: `BEDROCK_DATA_SOURCE_BUCKET` |

> **Note:** CUSTOM data source must be created on the KB beforehand (via console or CDK/CFN). Our code only calls the ingestion API on existing data sources.

**References:**
- [Ingest documents directly into a knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion.html)
- [IngestKnowledgeBaseDocuments API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html)
- [Connect to a custom data source](https://docs.aws.amazon.com/bedrock/latest/userguide/custom-data-source-connector.html)

