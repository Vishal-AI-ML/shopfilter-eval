# RAG Expansion Migration Plan

## Principles

- Additive before transformative.
- Preserve IDs, history, published versions, and artifact readers.
- One schema/runtime capability per verified checkpoint.
- Upgrade from an existing database and migrate from an empty database in tests.
- Do not combine pgvector infrastructure, provider secrets, knowledge ingestion, and assistant runtime in one migration.

## Stage 0 — Documentation only

Deliver ADR 0002, compatibility review, migration plan, threat model, and architecture update.

Database and runtime impact: none.

## Stage 1 — Generalize existing system metadata

Proposed additive columns on the existing system tables:

```txt
search_systems.system_type
search_systems.description
search_systems.status
search_system_versions.capabilities
search_system_versions.content_hash
search_system_versions.status
```

Backfill all existing rows as `LEXICAL_SEARCH` or their evidence-supported adapter type. Do not infer semantic/RAG capabilities from provider names.

Application terminology becomes AI System. Existing ORM/table names may remain temporarily to avoid a risky cross-cutting rename.

Compatibility:

- Existing search routes continue unchanged.
- New AI-system routes address the same persisted IDs.
- Existing jobs and runs continue to reference the same version IDs.

## Stage 2 — Providers, models, and prompts

Add metadata-only domains:

```txt
provider_configs
model_configs
prompt_definitions
prompt_versions
```

Provider configs store an opaque secret reference, never a raw secret. No external model is invoked in this stage.

## Stage 3 — Knowledge sources and immutable knowledge bases

Add:

```txt
knowledge_sources
knowledge_source_versions
knowledge_documents
knowledge_chunks
knowledge_bases
knowledge_base_versions
knowledge_base_catalogs
knowledge_base_sources
```

Catalog versions remain canonical and are linked into knowledge-base versions. Document artifacts remain in MinIO/S3 with content and artifact hashes.

No embeddings are generated yet.

## Stage 4 — pgvector and embedding indexes

Prerequisites:

1. Select and pin a PostgreSQL image that includes a PostgreSQL-17-compatible pgvector extension.
2. Verify Compose config and clean startup.
3. Verify upgrade against a copy of the existing volume/data.
4. Add `CREATE EXTENSION IF NOT EXISTS vector` in a dedicated Alembic migration.
5. Add embedding index records and vector storage.

Proposed domains:

```txt
embedding_configs
embedding_indexes
chunk_embeddings
```

Each embedding row is bound to the chunk hash, provider/model version, dimensionality, normalization policy, and index version. Repeated indexing is idempotent.

Rollback must not delete source documents, chunks, catalogs, datasets, or evaluation history.

## Stage 5 — RAG case schemas and artifact version 2

Add dataset and case kinds while keeping search cases valid. Introduce artifact schema v2 with:

```txt
retrieved chunks and products
reranked order
structured answer
citations
abstention result
tool invocations
conversation state deltas
judge results
token usage
component latency
```

Readers dispatch by schema version. Schema v1 artifacts remain immutable and readable.

## Stage 6 — Assistant sessions, citations, and tools

Add:

```txt
assistant_sessions
assistant_turns
retrieval_evidence
citations
tool_invocations
```

Initial tools are read-only and allow-listed. Session retention and deletion behavior must be documented before persistence is enabled.

## Stage 7 — Generalized evaluation jobs

Only after artifact v2 and AI-system versions are stable:

- Add a job/evaluation target kind.
- Add RAG-specific immutable input references.
- Preserve current search job requests.
- Extend the worker through separate executors rather than branching one monolithic runner.

## Stage 8 — Safety, regression, and online sampling

Add versioned safety cases, judge configurations/results, regression comparisons, quality-gate versions, and sampled online evaluation records.

Online samples never become golden truth without review.

## Migration validation matrix

Every schema checkpoint must prove:

| Scenario | Required evidence |
| --- | --- |
| Empty database | Alembic reaches head |
| Existing database | Upgrade preserves row counts and IDs |
| Seed/import repeat | Idempotent result |
| Cross-tenant access | Hidden or denied as designed |
| Downgrade, when supported | No unrelated data loss |
| Docker | Services healthy with pinned images |
| Logs | No secrets, tracebacks, or raw credentials |
| Tests | Ruff, Mypy, focused tests, full suite |

## Explicitly deferred

- Physical rename of `search_systems` tables.
- Removal of old search routes or job fields.
- Cloud-provider credentials UI.
- Action-taking commerce tools.
- Long-term personal memory.
- Automatic ingestion of raw production conversations into goldens.
