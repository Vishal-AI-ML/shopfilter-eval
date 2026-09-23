# Architecture

ShopFilter Eval is a local-first evaluation platform for e-commerce text search.

Milestone 1 includes domain models, a demo catalog, deterministic query parsing, a demo search engine, metrics, failure classification, and a CLI.

PostgreSQL, Redis, frontend, and AWS will be added only after the local evaluation core is stable.

Phase 13 adds a pinned, checksum-verified Amazon ESCI English-subset preparation pipeline. Raw data remains immutable and untracked; processed catalogs, draft judgments, provenance, and quality reports are versioned artifacts.

Phase 14 introduces a tenant-aware FastAPI persistence boundary. PostgreSQL stores organizations, projects, catalog and dataset versions, products, and evaluation cases. Alembic owns schema evolution. Tenant-owned queries require an explicit organization identifier until Phase 15 replaces the temporary header boundary with authenticated membership and RBAC.
