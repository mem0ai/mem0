# Store Document Tool Guide

The `store_document` MCP tool allows you to store large documents (markdown files, code files, essays, documentation, etc.) in your memory system. This is perfect for preserving entire documents that you want to reference later.

## Overview

Unlike `add_memories` which is for smaller pieces of information, `store_document` is designed for:
- 📄 **Large markdown files** (README files, documentation, blog posts)
- 💻 **Code files** (entire scripts, configuration files)
- 📝 **Essays and articles** (long-form content)
- 📚 **Documentation** (API docs, manuals, guides)
- 📋 **Meeting notes** (detailed notes from long meetings)

## Key Features

- **Full content preservation**: Stores the complete document without truncation
- **Automatic summarization**: Creates searchable summary memories automatically
- **Document chunking**: Breaks large documents into searchable chunks
- **Metadata support**: Store custom metadata about your documents
- **Type classification**: Organize documents by type (markdown, code, notes, etc.)
- **Search integration**: Documents are searchable via all memory search tools

## Usage Examples

### 1. Store a Markdown File

```
store_document(
    title="Project README",
    content="""# My Awesome Project

## Overview
This project does amazing things...

## Installation
```bash
npm install awesome-project
```

## Usage
Here's how to use it:
...
""",
    document_type="markdown"
)
```

### 2. Store Code Files

```
store_document(
    title="Database Configuration Script",
    content="""#!/bin/bash
# Database setup script for production

DB_HOST="localhost"
DB_PORT=5432
DB_NAME="myapp_prod"

# Create database
createdb $DB_NAME

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
""",
    document_type="code",
    metadata={
        "language": "bash",
        "environment": "production",
        "author": "DevOps Team"
    }
)
```

### 3. Store Documentation

```
store_document(
    title="API Documentation v2.1",
    content="""# API Documentation

## Authentication
All API endpoints require authentication via Bearer tokens...

## Endpoints

### GET /api/users
Returns a list of users...

### POST /api/users
Creates a new user...
""",
    document_type="documentation",
    source_url="https://docs.mycompany.com/api/v2.1",
    metadata={
        "version": "2.1",
        "category": "API",
        "last_updated": "2024-01-15"
    }
)
```

### 4. Store Meeting Notes

```
store_document(
    title="Q1 Strategy Planning Meeting - Jan 15, 2024",
    content="""# Q1 Strategy Planning Meeting

**Date**: January 15, 2024
**Attendees**: Alice, Bob, Carol, David

## Key Decisions
1. Launch new product feature in March
2. Hire 2 additional developers
3. Increase marketing budget by 20%

## Action Items
- [ ] Alice: Finalize product specifications by Jan 25
- [ ] Bob: Create hiring plan by Feb 1
- [ ] Carol: Draft marketing budget proposal by Jan 20

## Next Meeting
February 1, 2024 at 2 PM PST
""",
    document_type="notes",
    metadata={
        "meeting_type": "strategy",
        "quarter": "Q1_2024",
        "attendees": ["Alice", "Bob", "Carol", "David"]
    }
)
```

### 5. Store Research Papers or Essays

```
store_document(
    title="The Future of AI in Healthcare",
    content="""# The Future of AI in Healthcare

## Abstract
Artificial Intelligence is transforming healthcare delivery...

## Introduction
The healthcare industry stands at the precipice of a technological revolution...

## Current Applications
### Medical Imaging
AI-powered diagnostic tools are already showing promise...

### Drug Discovery
Machine learning algorithms are accelerating pharmaceutical research...

## Challenges and Limitations
Despite the promise, several challenges remain...

## Conclusion
The integration of AI in healthcare represents both an opportunity and a responsibility...
""",
    document_type="research",
    source_url="https://example.com/ai-healthcare-paper",
    metadata={
        "author": "Dr. Jane Smith",
        "publication_date": "2024-01-10",
        "field": "Healthcare AI",
        "word_count": 5000
    }
)
```

## Parameter Reference

### Required Parameters
- **`title`**: A descriptive title for the document
- **`content`**: The full text content (minimum 100 characters)

### Optional Parameters
- **`document_type`**: Type classification (default: "markdown")
  - Common types: `markdown`, `code`, `notes`, `documentation`, `research`, `essay`
- **`source_url`**: URL where the document originated
- **`metadata`**: Custom metadata object with any additional information

## How It Works Behind the Scenes

1. **Document Storage**: Full content is stored in PostgreSQL database
2. **Summary Creation**: A concise summary is created and stored as a searchable memory
3. **Document Chunking**: Large documents are broken into chunks for better search
4. **Linking**: The document and summary memory are linked together
5. **Search Integration**: Content becomes searchable via all memory search tools

## Searching Stored Documents

Once stored, you can find your documents using any of these search tools:

### Quick Search
```
search_memory("project README")
search_memory("database configuration")
search_memory("Q1 strategy meeting")
```

### Comprehensive Analysis
```
deep_memory_query("What were the key decisions from our strategy meetings?")
deep_memory_query("Show me all the API documentation I've stored")
```

### Browse All Content
```
list_memories(limit=50)  # Will include document summaries
```

## Best Practices

### 1. Use Descriptive Titles
```
✅ Good: "React Component Library Documentation v3.2"
❌ Bad: "docs"
```

### 2. Choose Appropriate Document Types
```
✅ Good: document_type="code" for scripts
✅ Good: document_type="research" for papers
✅ Good: document_type="notes" for meeting notes
```

### 3. Add Useful Metadata
```python
metadata={
    "author": "John Doe",
    "version": "1.0",
    "category": "frontend",
    "last_updated": "2024-01-15",
    "tags": ["react", "components", "ui"]
}
```

### 4. Include Source URLs When Available
```python
source_url="https://github.com/myorg/project/blob/main/README.md"
```

## Size Limits and Performance

- **No hard size limit**: PostgreSQL TEXT fields can handle very large documents
- **Recommended range**: 100 characters to 1MB per document
- **Chunking**: Large documents are automatically chunked for better search performance
- **Memory efficiency**: Only summaries are stored in vector memory, full content in SQL

## Integration with Other Tools

Documents stored with `store_document` work seamlessly with:
- `search_memory`: Find documents by keywords
- `deep_memory_query`: Analyze document content with AI
- `ask_memory`: Ask questions about document content
- Web dashboard: View and manage stored documents

## Error Handling

The tool provides helpful error messages:

```
Error: Document title is required
Error: Document content is required  
Error: Content too short. For small content, use 'add_memories' instead.
Error: App {app_name} is currently paused. Cannot store new documents.
```

## Example Response

When successful, you'll get a detailed JSON response:

```json
{
  "success": true,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Project README",
  "document_type": "markdown",
  "content_length": 2547,
  "word_count": 425,
  "message": "Successfully stored document 'Project README' (2,547 characters). Document is now searchable via memory tools.",
  "search_tip": "You can find this document by searching for 'Project README' or key topics from the content."
}
```

## Comparison with Other Tools

| Tool | Best For | Size Limit | Search Type |
|------|----------|------------|-------------|
| `add_memories` | Short facts, preferences | Small (< 1000 chars) | Semantic |
| `store_document` | Large documents, files | Very large (> 100 chars) | Full-text + Semantic |
| `sync_substack_posts` | Substack essays | N/A (automatic) | Semantic |

## Getting Started

Try storing your first document:

```
store_document(
    title="My First Stored Document",
    content="# Welcome to Document Storage\n\nThis is my first document stored in the memory system. I can now search for it later and reference its content in conversations.",
    document_type="notes"
)
```

Then search for it:
```
search_memory("first stored document")
```

This powerful tool transforms your memory system into a comprehensive document repository that you can search, reference, and analyze with AI assistance! 