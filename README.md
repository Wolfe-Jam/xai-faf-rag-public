<!-- faf: xai-faf-rag-public | markdown | doc | Public About Repo for FAF RAG / LazyRAG — source code private at Wolfe-Jam/xai-faf-rag. -->
<!-- faf: doc=readme | canonical=project.faf | family=FAF | private_source=Wolfe-Jam/xai-faf-rag -->

[![FAF](https://mcpaas.live/badge/Wolfe-Jam/xai-faf-rag-public.svg)](https://builder.faf.one)
[![IANA Registered](https://img.shields.io/badge/IANA-application%2Fvnd.faf%2Byaml-blue)](https://www.iana.org/assignments/media-types/application/vnd.faf+yaml)

> 📖 **Public About Repo** — this is the public face of `Wolfe-Jam/xai-faf-rag` (source private). README, docs, project.faf — no source code. Same shape as Anthropic's [`claude-code`](https://github.com/anthropics/claude-code) repo: public face, private engine.

# xai-faf-rag

Cache-first RAG using Grok Collections + LAZY-RAG caching.

## Overview

Hybrid RAG system combining LAZY-RAG caching layer with Grok Collections native RAG. Uploads .faf files to Collections, provides cache-first retrieval, and integrates with Grok chat.

```
Query
  |
  v
LAZY-RAG Cache (0.003ms, FREE)
  |-- HIT (60-78%) --> Return immediately
  |-- MISS --> Grok Collections API ($2.50/1K searches)
                    |
                    v
               Cache result --> Return
```

## Installation

```bash
pip install xai-sdk --upgrade  # v1.4.0+ required
```

## Quick Start

```python
from src.integrator import XAIFafRag

# Set environment variables
# XAI_API_KEY - for reads/search
# XAI_MANAGEMENT_API_KEY - for writes/upload

# Initialize
integrator = XAIFafRag()

# Upload .faf and supporting docs
integrator.sync_faf("project.faf", supporting=["docs.pdf"])

# Search directly
results = integrator.search("project constraints")

# RAG-enhanced chat (Grok retrieves autonomously)
response = integrator.query("What are the project goals?")
print(response)
```

## API Reference

### XAIFafRag

```python
XAIFafRag(
    api_key=None,              # XAI_API_KEY env var
    management_api_key=None,   # XAI_MANAGEMENT_API_KEY env var
    collection_name=None,      # Default: "FAF Elite Palace"
    enable_cache=True          # LAZY-RAG cache layer
)
```

#### Methods

| Method | Description |
|--------|-------------|
| `sync_faf(faf_path, supporting=[])` | Upload .faf and supporting files |
| `search(query, num_results=5, retrieval_mode="hybrid")` | Direct collection search |
| `query(question, model=None, system_prompt=None)` | RAG-enhanced chat |
| `clear_cache()` | Clear the in-memory cache |
| `cache_stats()` | Get cache statistics |

#### Retrieval Modes

- `hybrid` (recommended) - Combined semantic + keyword
- `semantic` - Embedding-based similarity
- `keyword` - Traditional keyword matching

## Architecture

7-Layer xAI-FAF-RAG Stack:

| Layer | Component | Purpose |
|-------|-----------|---------|
| 1 | Authentication | Dual key (api_key + management_api_key) |
| 2 | Persistent Context | project.faf (IANA YAML) |
| 3 | Knowledge Base | Grok Collections (native RAG) |
| 4 | Sync & Healing | Bi-directional delta sync |
| 5 | Agent Orchestration | collections_search tool-calling |
| 6 | Security | Offline-first, E2E encryption |
| 7 | Scale | Stateless MCP, edge execution |

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `XAI_API_KEY` | Yes | API key for reads/search |
| `XAI_MANAGEMENT_API_KEY` | Yes | API key for writes/upload |

## Requirements

- Python 3.10+
- xai-sdk v1.4.0+

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=src  # With coverage
```

## Value Proposition

- **Cost Reduction**: 60-78% fewer API calls via caching
- **Speed**: 0.003ms cache hits vs API latency
- **Quality**: .faf structured context = better retrieval
- **Cross-platform**: Cache layer works with any backend

## License

Proprietary - Do not publish.
