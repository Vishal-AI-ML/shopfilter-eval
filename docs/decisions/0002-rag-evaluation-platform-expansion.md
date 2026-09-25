# ADR 0002: Expand ShopFilter Eval to grounded RAG evaluation

Status: Accepted

Date: 2026-09-25

## Context

ShopFilter Eval already has a deterministic, multi-tenant foundation for product-search evaluation: immutable catalogs and datasets, provider-agnostic search adapters, relevance and constraint metrics, evidence-backed failures, durable workers, immutable artifacts, Langfuse-compatible tracing, RBAC, and project-scoped frontend flows.

The intended portfolio and product outcome also requires visible applied-AI capabilities: knowledge ingestion, semantic and hybrid retrieval, reranking, grounded generation, citations, structured outputs, tool calling, conversational state, RAG evaluation, calibrated LLM judgments, and prompt-injection security.

Replacing the repository or weakening deterministic search evaluation would discard proven controls and create unnecessary risk. Treating a shopping assistant as an unrelated consumer chatbot would also broaden the product beyond its B2B evaluation purpose.

## Decision

Expand ShopFilter Eval into a B2B evaluation, observability, and release-quality platform for e-commerce search systems and grounded RAG shopping assistants.

The existing search-evaluation core remains authoritative and becomes the retriever and hard-constraint evaluation layer. A hosted reference shopping assistant will demonstrate the full RAG path, while provider-agnostic adapters will allow customer search and assistant systems to be evaluated.

The application-level term will become **AI System**. Existing physical `search_systems` and `search_system_versions` tables and API behavior will be retained during the first compatibility stage. New system kinds and capabilities will be added without destructive renames. The old `/v1/search-systems` routes will remain supported as compatibility aliases when `/v1/ai-systems` is introduced.

RAG evaluation will use three levels:

1. Component: retriever, reranker, generator, tools, and conversation state.
2. Pipeline: context relevance, faithfulness, answer relevance, citations, constraints, and abstention.
3. Application: correctness, completeness, helpfulness, safety, latency, cost, and reliability.

Evaluation methods will remain explicit:

- Programmatic checks for mechanically verifiable evidence.
- Human review for trusted nuanced labels.
- Calibrated LLM-as-judge only for semantic criteria that cannot be decided deterministically.

Local Ollama integrations will be provider-based, optional, and disabled by default. Hard deterministic failures cannot be overridden by model judgments.

## Consequences

### Positive

- Existing search work is preserved and reused.
- RAG capabilities become measurable rather than demo-only.
- Every candidate can be compared against immutable baselines.
- The portfolio demonstrates applied AI plus production backend depth.
- Customer and hosted systems share one evaluation contract.

### Costs

- Additional versioned domains are required for knowledge, prompts, providers, conversations, citations, and judgments.
- Existing search-specific names must be generalized carefully.
- PostgreSQL must gain pgvector through a separately reviewed, pinned image/migration checkpoint.
- Human review is required for assistant and judge-calibration datasets.

## Rejected alternatives

### Restart as a new RAG repository

Rejected because it would duplicate authentication, tenancy, workers, artifacts, metrics, tracing, and review infrastructure.

### Build a public consumer marketplace

Rejected because checkout, payments, orders, and consumer operations do not improve the evaluation product and create large unrelated risk.

### Rename all search tables immediately

Rejected for the first compatibility stage because jobs, runs, imports, tests, and APIs reference search-system identifiers deeply. Semantic generalization is safer than an immediate physical rename.

### Make an LLM judge authoritative

Rejected because catalog constraints, product existence, citations, authorization, and operational measurements are deterministic facts.

## Invariants

- Existing published versions and artifacts remain immutable.
- Existing search runs remain readable.
- Migrations are additive and backward compatible.
- Retrieved content is untrusted data, never an instruction source.
- Secrets never appear in browser bundles, logs, artifacts, or chat.
- No RAG quality claim is made without a versioned dataset and reproducible run.
