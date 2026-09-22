# ADR 0001: Local-first evaluation core

Status: Accepted

Decision: Build and test the deterministic local evaluation core before adding PostgreSQL, Redis, frontend, cloud deployment, or an LLM judge.

Reason: This keeps the first milestone reproducible, fast to test, and independent of external infrastructure.
