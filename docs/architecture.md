# Architecture

ShopFilter Eval is a local-first evaluation platform for e-commerce text search.

Milestone 1 includes domain models, a demo catalog, deterministic query parsing, a demo search engine, metrics, failure classification, and a CLI.

PostgreSQL, Redis, frontend, and AWS will be added only after the local evaluation core is stable.

Phase 13 adds a pinned, checksum-verified Amazon ESCI English-subset preparation pipeline. Raw data remains immutable and untracked; processed catalogs, draft judgments, provenance, and quality reports are versioned artifacts.
