# Architecture

ShopFilter Eval is a production-oriented, multi-tenant evaluation, observability, and release-quality platform for e-commerce search systems and grounded RAG shopping assistants.

## Architectural invariants

- PostgreSQL is the canonical business database.
- Redis is queue, notification, and ephemeral coordination infrastructure.
- MinIO/S3 stores immutable artifacts; hashes remain independently verifiable.
- Langfuse stores traces, not canonical datasets, metrics, failures, or verdicts.
- Published catalogs, datasets, knowledge versions, system versions, prompts, and run artifacts are immutable.
- Deterministic evidence is authoritative for product existence, constraints, citations, authorization, and operational measurements.
- Human-reviewed labels are the semantic source of truth.
- LLM judgments are optional, versioned, calibrated, and unable to override hard failures.
- Retrieved content is untrusted data and cannot modify system policy or tool permissions.

## Runtime topology

```text
Next.js web
    ↓ same-origin BFF
FastAPI API
    ↓
PostgreSQL + Redis + Worker + MinIO/S3
    ↓
Provider boundaries
├── Search / Assistant Adapter
├── Embedding Provider
├── Reranker Provider
├── Generator Provider
├── Semantic Judge Provider
└── Trace Provider
```

The hosted reference RAG path is:

```text
message
→ session context
→ intent and hard constraints
→ lexical + semantic retrieval
→ hybrid fusion
→ hard filtering
→ reranking
→ context construction
→ structured generation
→ citation and constraint verification
→ grounded response
```

## Evaluation architecture

Evaluation is separated into three levels:

1. Component: retriever, reranker, generator, tools, and conversation state.
2. Pipeline: context relevance, faithfulness, answer relevance, citations, constraints, and abstention.
3. Application: correctness, completeness, helpfulness, safety, latency, cost, and reliability.

Programmatic, human, and LLM-judge evidence remain distinguishable in storage and UI. Failures identify the earliest observable failure supported by evidence rather than claiming an unproven root cause.

## Evolution from the search foundation

The deterministic local evaluation core remains the base. Existing domain models, demo search, SearchAdapter, relevance metrics, failure classification, CLI, tracing, persistence, durable workers, authentication, RBAC, and frontend shell are reused.

The application term expands from Search System to AI System. Physical search-system tables and compatibility APIs are retained during the first migration stage because historical runs and durable jobs reference those IDs. New knowledge, provider, prompt, assistant, citation, and RAG-evaluation domains are introduced additively.

PostgreSQL pgvector is introduced only through a dedicated, pinned-image checkpoint that proves clean migration and existing-data upgrade. Local Ollama integrations are provider-based, optional, and disabled by default.

See:

- `docs/decisions/0001-local-first-evaluation-core.md`
- `docs/decisions/0002-rag-evaluation-platform-expansion.md`
- `docs/rag-scope-compatibility.md`
- `docs/rag-migration-plan.md`
- `docs/rag-threat-model.md`
