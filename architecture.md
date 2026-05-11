# xAI-FAF-RAG Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Elite Palace                           │
│                   xAI-FAF-RAG Stack                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────┐                                               │
│   │  Query  │                                               │
│   └────┬────┘                                               │
│        │                                                    │
│        ▼                                                    │
│   ┌─────────────────────────────────────┐                   │
│   │       LAZY-RAG Cache Layer          │                   │
│   │  (0.003ms lookups | 60-78% hit rate | FREE)            │
│   └────────────────┬────────────────────┘                   │
│                    │                                        │
│         ┌─────────┴─────────┐                               │
│         │                   │                               │
│        HIT                MISS                              │
│         │                   │                               │
│         ▼                   ▼                               │
│   ┌──────────┐    ┌─────────────────────┐                   │
│   │  Return  │    │  Grok Collections   │                   │
│   │ (cached) │    │    (hybrid search)  │                   │
│   └──────────┘    └──────────┬──────────┘                   │
│                              │                              │
│                              ▼                              │
│                    ┌─────────────────┐                      │
│                    │  Cache Result   │                      │
│                    │    & Return     │                      │
│                    └─────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

| Step | Component | Latency | Cost |
|------|-----------|---------|------|
| 1 | Query received | - | - |
| 2 | LAZY-RAG cache check | 0.003ms | FREE |
| 3a | Cache HIT → Return | 0.003ms | FREE |
| 3b | Cache MISS → Grok API | ~50ms | $2.50/1K |
| 4 | Cache result | <1ms | FREE |

## Components

### LAZY-RAG Cache
- In-memory HashMap (Python) / RwLock<HashMap> (Rust)
- SHA256 cache keys
- 60-78% expected hit rate

### Grok Collections
- Hybrid search (semantic + keyword)
- .faf files as text/yaml
- Managed embeddings (grok-embedding-small)

### Dual Authentication
- `XAI_API_KEY` → Reads/Search
- `XAI_MANAGEMENT_API_KEY` → Writes/Upload

## Tech Stack

| Layer | Python | Rust |
|-------|--------|------|
| HTTP Client | xai-sdk | reqwest |
| Cache | dict | RwLock<HashMap> |
| CLI | argparse | clap |
| Async | - | tokio |

## Collection Contents

- `project.faf` — Eternal DNA
- `grok.md` — Agent persona
- `skills.md` — Tool primitives
- `architecture.png` — Visual diagram
- `architecture.md` — This document (tiny/shareable)

---

**Verified:** 2026-01-02 | All docs verified. No errors.
