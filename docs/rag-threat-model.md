# RAG Threat Model

## Scope

This threat model covers tenant-scoped knowledge ingestion, retrieval, generation, citations, tool calling, evaluation, tracing, and external adapters. It supplements the existing authentication, RBAC, session, artifact, and tenant-isolation controls.

## Trust boundaries

1. Browser to same-origin Next.js BFF.
2. BFF to FastAPI with authenticated session and organization context.
3. API/worker to PostgreSQL, Redis, and MinIO/S3.
4. Ingestion parser to untrusted uploaded content.
5. Retrieval context to generator.
6. Generator to allow-listed tools.
7. API/worker to local or external AI providers.
8. Trace exporter to Langfuse.
9. Customer adapter to external search/assistant endpoints.

## Protected assets

- Tenant catalogs, documents, embeddings, prompts, goldens, and evaluation results.
- Provider credentials and secret references.
- System prompts and guardrail policies.
- User identity, sessions, and review attribution.
- Immutable evidence, artifacts, and provenance.
- Tool authorization and external endpoint policy.

## Threats and required controls

### Direct prompt injection

Threat: user asks the model to ignore policy, reveal prompts, or perform an unauthorized action.

Controls:

- Fixed system policy outside user content.
- Structured-output validation.
- Allow-listed read-only tools.
- Refusal and scope evals.
- No raw secrets in model context.

### Indirect injection and knowledge poisoning

Threat: malicious instructions are embedded in PDFs, product descriptions, reviews, or other indexed content.

Controls:

- Treat retrieved text as quoted evidence, not instructions.
- Preserve source provenance and content hashes.
- Restrict source writers through RBAC.
- Scan/flag suspicious content without claiming perfect detection.
- Maintain adversarial goldens with poisoned documents.
- Never let retrieved content change tool policy or system configuration.

### Cross-tenant retrieval

Threat: a query retrieves another organization’s chunks, products, prompts, or traces.

Controls:

- Organization and project IDs on every tenant-owned record.
- Tenant filter included in every vector and relational query.
- No global vector search followed by post-filtering.
- Cross-tenant tests at API, worker, and retrieval layers.
- Non-member resource existence remains hidden.

### Hallucinated products, attributes, prices, or policies

Controls:

- Validate product IDs against the exact catalog version.
- Verify hard attributes programmatically.
- Require source citations for factual claims.
- Permit explicit abstention.
- Prevent an LLM judge from overriding deterministic failures.

### Citation spoofing

Threat: response cites a real source that does not support the claim, or cites a source from another version.

Controls:

- Persist claim-to-source mapping.
- Verify source and version membership.
- Evaluate citation precision and completeness.
- Display missing/unsupported evidence distinctly.

### Tool misuse

Threat: wrong tool, wrong arguments, excessive calls, or attempts to perform mutations.

Controls:

- Read-only tool set for V1.
- Typed argument schemas and server-side authorization.
- Per-turn call and recursion limits.
- Timeout and response-size budgets.
- Store tool traces without secrets.
- Treat tool output as untrusted data.

### External adapter SSRF and data exfiltration

Controls:

- HTTPS validation.
- Host allowlists.
- Private/reserved IP blocking.
- DNS rebinding and redirect restrictions.
- Request and response size limits.
- Safe authentication injection on the server only.
- Redacted errors and logs.

### PII and secret leakage

Controls:

- Minimize persisted conversation data.
- Redact logs/traces and model context where required.
- Configure retention and deletion before long-term memory.
- Store opaque secret references, not raw credentials.
- Test prompt/system/credential extraction attacks.

### Resource exhaustion and cost abuse

Controls:

- Upload, chunk, context, output-token, tool-call, retry, and timeout limits.
- Job idempotency and cancellation.
- Per-tenant rate and cost budgets before public exposure.
- Queue depth and worker health monitoring.

### Model/provider failure

Controls:

- Provider timeouts and normalized errors.
- Retry only when explicitly safe.
- Circuit/fallback behavior that does not fabricate answers.
- Provider outage does not corrupt canonical run state.

### Evaluation manipulation

Threat: changing datasets, prompts, judge versions, or thresholds to hide regressions.

Controls:

- Immutable published datasets and system versions.
- Versioned metric definitions, judge rubrics, and gates.
- Audit logs and reviewer attribution.
- Baseline/candidate evidence retained together.
- Judge-noise thresholds derived from repeated unchanged runs.

## Security evaluation packs

The first safety dataset includes:

```txt
10 direct prompt injections
10 indirect injections / poisoned sources
10 scope or harmful-output cases
10 PII or cross-tenant leakage cases
10 tool abuse or resource-exhaustion cases
```

## Deferred risks

Checkout, payments, refunds, order changes, and autonomous purchase actions are out of initial scope. If action-taking tools are introduced, they require a new threat model, explicit user confirmation, transaction limits, idempotency, audit evidence, and rollback/compensation design.
