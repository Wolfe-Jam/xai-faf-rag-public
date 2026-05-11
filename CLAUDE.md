# CLAUDE.md - xai-faf-rag

## PROJECT STATE: ACTIVE
**Mission:** Cache-first RAG using Grok Collections + LAZY-RAG

---

## Quick Start

```bash
# Install dependencies
pip install xai-sdk --upgrade  # v1.4.0+ required

# Set environment variables
export XAI_API_KEY="your_api_key"
export XAI_MANAGEMENT_API_KEY="your_management_key"

# Run tests
python -m pytest tests/
```

---

## Architecture

```
Query
  |
  v
LAZY-RAG Cache (0.003ms, FREE)
  |-- HIT (60-78%) --> Return immediately
  |-- MISS --> Grok Collections API
                    |
                    v
               Cache result --> Return
```

---

## Verified API Reference (2026-01-02)

### Authentication

```python
from xai_sdk import Client

client = Client(
    api_key=os.getenv("XAI_API_KEY"),              # Reads
    management_api_key=os.getenv("XAI_MANAGEMENT_API_KEY")  # Writes
)
```

### Collections Operations

```python
# Create
collection = client.collections.create(
    name="FAF Project DNA",
    model_name="grok-embedding-small"
)

# Upload .faf
client.collections.upload_document(
    collection_id=collection.collection_id,
    name="project.faf",
    data=faf_bytes,
    content_type="text/yaml"
)

# Search
results = client.collections.search(
    query="project constraints",
    collection_ids=[collection.collection_id],
    retrieval_mode="hybrid",
    num_results=5
)

# List
collections = client.collections.list().data
```

### RAG in Chat

```python
from xai_sdk.chat import user, system
from xai_sdk.tools import collections_search

chat = client.chat.create(
    model="grok-4-fast",
    messages=[
        system("Use collection for context."),
        user("What are the project goals?")
    ],
    tools=[
        collections_search(
            collection_ids=[collection.collection_id],
            retrieval_mode="hybrid"
        )
    ]
)
response = chat.sample()
print(response.content)
```

### Error Handling

```python
from xai_sdk import APIError, RateLimitError, AuthenticationError

try:
    # operations
except RateLimitError:
    time.sleep(10)
    # retry
except AuthenticationError:
    # check keys
except APIError as e:
    print(e.status_code, e.message)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/client.py` | xAI client wrapper with dual auth |
| `src/collections.py` | Collections management |
| `src/cache.py` | LAZY-RAG cache layer |
| `src/integrator.py` | Main FAFGrokRAGIntegrator class |
| `tests/test_integrator.py` | Unit + integration tests |

---

## Development Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src

# Type check
mypy src/

# Lint
ruff check src/
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `XAI_API_KEY` | Yes | API key for reads/search |
| `XAI_MANAGEMENT_API_KEY` | Yes | API key for writes/upload |

---

## Constraints

- Python 3.10+ required
- xai-sdk v1.4.0+ required
- .faf files should be <1MB to preserve YAML structure
- PROPRIETARY - do not publish

---

## Reference Docs

- Verified API: `/Users/wolfejam/RAG/01-STRATEGY/GROK-COLLECTIONS-SNAG-LIST.md`
- xAI Docs: https://docs.x.ai/docs/guides/using-collections/api
- Collections Search Tool: https://docs.x.ai/docs/guides/tools/collections-search-tool

---

## Current Focus

1. Implement core `FAFGrokRAGIntegrator` class
2. Add LAZY-RAG cache layer
3. Write comprehensive tests
4. Benchmark cache hit rates

---

**STATUS: BI-SYNC ACTIVE**

*For Grok. For the rockets. For Mars.*
