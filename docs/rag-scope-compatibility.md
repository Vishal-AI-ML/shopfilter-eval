# RAG Scope and Compatibility Review

## Purpose

This document maps the verified ShopFilter Eval repository at Git checkpoint `b6727c4` to the approved RAG-first product direction. It is a design checkpoint only: no runtime behavior, database schema, dependency, provider, or Docker image is changed here.

## Repository evidence reviewed

- 291 archived repository entries, 134 Python files, 38 TSX files, and 23 TypeScript files.
- Ten Alembic migrations through organization invitations.
- Existing `search_systems`, `search_system_versions`, `evaluation_runs`, and `evaluation_jobs` persistence.
- Twenty-four source/test/frontend files referencing search-system concepts.
- Fifteen API/worker references to `search_system_version_id`.
- PostgreSQL 17 Alpine without pgvector.
- Search-only domain contracts and run artifact schema version 1.

## Reusable foundation

| Existing capability | RAG use | Compatibility decision |
| --- | --- | --- |
| Organizations, projects, memberships, RBAC | Tenant and project isolation | Reuse unchanged |
| Catalogs, catalog versions, products | Structured product knowledge | Reuse as canonical product source |
| Dataset lifecycle and reviews | RAG goldens and human approval | Extend case payloads; preserve lifecycle |
| SearchAdapter | Retriever/search boundary | Keep; add assistant and AI-provider protocols beside it |
| Precision, Recall, MRR, NDCG | Retriever and reranker evaluation | Reuse unchanged |
| Constraint metrics | Hard product rules | Remain authoritative |
| Failure evidence | RAG diagnosis | Extend taxonomy without deleting old values |
| EvaluationRunner and artifacts | Offline suite foundation | Add new artifact schema versions; keep v1 readable |
| Evaluation jobs and workers | Async RAG evaluations | Generalize job target in stages |
| MinIO/S3 artifacts | Knowledge and run artifacts | Reuse content-addressed storage |
| Langfuse trace provider | RAG spans | Extend trace hierarchy |
| Catalog frontend | Knowledge ingestion entry point | Retain and link to Knowledge Sources |

## Compatibility risks

### 1. Search-system identity is deeply referenced

`search_system_version_id` is a non-null foreign key in runs and jobs and is loaded directly by the worker. Immediate renaming or replacement would affect API contracts, persistence, worker execution, imports, tests, and historical data.

Decision: use **AI System** as the application/API concept while retaining the physical search tables in the first stage. Add `system_type`, capabilities, status, and immutable configuration metadata. Introduce `/v1/ai-systems`; preserve `/v1/search-systems` as a compatibility alias for search-compatible system types.

### 2. Run artifacts are search-shaped

Artifact schema v1 requires `search_system_version`, product IDs, search metrics, and a top-k configuration.

Decision: never mutate schema v1. Introduce versioned artifact envelopes for RAG cases with component outputs, retrieved chunks, answer, citations, tool invocations, judge results, token usage, and latency breakdowns.

### 3. Evaluation cases use a flexible payload but a required query

The database can retain varied expectations in JSON, but the current domain model only understands a single search query and expected products.

Decision: add explicit dataset/case kinds while preserving the existing search case. New RAG case models will support single-turn and multi-turn inputs, expected sources, required and forbidden claims, expected citations, tool expectations, and abstention behavior.

### 4. PostgreSQL lacks pgvector

The current Compose image is `postgres:17-alpine`; adding vector columns before the extension and image are verified would break clean migrations.

Decision: pgvector gets its own checkpoint with a pinned image, extension migration, empty-database test, existing-volume upgrade test, rollback plan, and real Docker acceptance.

### 5. Provider secrets do not yet have a domain

Decision: provider records store public metadata and an opaque `secret_ref`; raw provider credentials belong in environment/Secrets Manager and never in general configuration JSON.

## Target bounded contexts

### AI Systems

Application-level abstraction for lexical, semantic, hybrid, hosted RAG, external search, and external assistant systems.

### Knowledge

- `knowledge_sources`: named project sources and source kind.
- `knowledge_source_versions`: immutable parsed artifacts and provenance.
- `knowledge_documents`: logical documents inside a version.
- `knowledge_chunks`: deterministic chunks and hashes.
- `knowledge_bases`: named aggregates.
- `knowledge_base_versions`: immutable retrieval corpora.
- `knowledge_base_catalogs`: catalog-version membership.
- `knowledge_base_sources`: document-source membership.
- `embedding_indexes`: model/config-bound index versions.

Catalogs remain canonical; they are referenced by knowledge-base versions rather than copied into document tables.

### Providers, models, and prompts

- Provider config: provider kind, display name, endpoint policy, secret reference.
- Model config: provider, purpose, model identifier, safe public parameters.
- Prompt definition/version: immutable template, variables, rubric/schema version, hash.

### Assistant runtime

- Sessions and turns.
- Retrieved evidence and citations.
- Read-only tool invocations.
- Structured answers and abstentions.

### Evaluation

Existing deterministic metrics remain. New component/pipeline/application results use versioned metric definitions and retain human, deterministic, and judgment evidence separately.

## API compatibility

### Preserve

- Existing `/v1/search-systems` behavior.
- Existing evaluation-job request fields during the compatibility window.
- Existing run detail responses and artifact readers.

### Add later

- `/v1/ai-systems`
- `/v1/knowledge-sources`
- `/v1/knowledge-bases`
- `/v1/prompts`
- `/v1/assistant-sessions`
- `/v1/rag-evaluations`

### Deprecation policy

No route or field is removed in the RAG expansion. Deprecation requires a documented replacement, client migration, tests, and at least one released compatibility window.

## UI compatibility

The current project module card labelled Search Systems will become AI Systems only after the generalized API exists. Catalogs remain available. Planned modules are added in this order:

1. AI Systems
2. Knowledge Sources
3. Prompts
4. Assistant Playground
5. Datasets
6. Evaluation Runs
7. Failure Explorer
8. Regression
9. Online Monitoring

## Acceptance criteria for this checkpoint

- ADR records the product decision and invariants.
- Existing reusable domains and risks are documented.
- Physical table renames are explicitly deferred.
- Additive migration stages are documented.
- RAG trust boundaries and security controls are documented.
- Architecture documentation reflects the RAG-first direction.
- No runtime code, migration, dependency, lockfile, Docker image, or frontend behavior changes.
