"use client";

import { FormEvent, useMemo, useState } from "react";

import { errorMessage } from "@/lib/api-errors";
import type {
  AISystemWithVersions,
  AssistantPlaygroundResponse,
} from "@/lib/assistant-types";
import type { CatalogWithVersions } from "@/lib/catalog-types";
import type { ProjectSummary } from "@/lib/project-types";

const EXAMPLES = [
  "wireless charger",
  "phone case",
  "kitchen storage",
];

function compactHash(value: string | null): string {
  return value ? `${value.slice(0, 10)}…` : "not recorded";
}

function activeFilters(filters: Record<string, unknown> | null): [string, string][] {
  if (!filters) return [];
  return Object.entries(filters)
    .filter(([, value]) => value !== null && value !== "" && value !== false)
    .map(([key, value]) => [key.replaceAll("_", " "), String(value)]);
}

export function AssistantPlayground({
  organizationId,
  project,
  catalogs,
  systems,
}: {
  organizationId: string;
  project: ProjectSummary;
  catalogs: CatalogWithVersions[];
  systems: AISystemWithVersions[];
}): React.ReactElement {
  const catalogOptions = useMemo(
    () => catalogs.flatMap((catalog) => catalog.versions
      .filter((version) => version.status === "PUBLISHED")
      .map((version) => ({ catalog, version }))),
    [catalogs],
  );
  const systemOptions = useMemo(
    () => systems.flatMap((system) => system.versions
      .filter((version) => version.status === "PUBLISHED")
      .map((version) => ({ system, version }))),
    [systems],
  );
  const [catalogVersionId, setCatalogVersionId] = useState(
    catalogOptions[0]?.version.id ?? "",
  );
  const [systemVersionId, setSystemVersionId] = useState(
    systemOptions[0]?.version.id ?? "",
  );
  const [query, setQuery] = useState(EXAMPLES[0]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssistantPlaygroundResponse | null>(null);
  const ready = catalogOptions.length > 0 && systemOptions.length > 0;

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const response = await fetch("/api/organization/assistant-playground", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "content-type": "application/json",
          "x-organization-id": organizationId,
        },
        body: JSON.stringify({
          project_id: project.id,
          catalog_version_id: catalogVersionId,
          ai_system_version_id: systemVersionId,
          query,
          top_k: 5,
        }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(body, "Unable to run the reference assistant."));
        return;
      }
      setResult(body as AssistantPlaygroundResponse);
    } catch {
      setError("Assistant service is unavailable. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="assistant-layout">
      <section className="assistant-config" aria-labelledby="assistant-config-heading">
        <div>
          <p className="eyebrow">REFERENCE ASSISTANT</p>
          <h2 id="assistant-config-heading">Grounded catalog playground</h2>
          <p>
            This visible slice uses deterministic lexical retrieval and hard filters.
            LLM generation, vectors, and semantic claims are explicitly disabled.
          </p>
        </div>
        <div className="assistant-mode-card">
          <span className="assistant-live-dot" />
          <div><strong>Deterministic reference mode</strong><small>Generator disabled · no fake LLM output</small></div>
        </div>
      </section>

      {!ready ? (
        <section className="assistant-setup-state">
          <span>SETUP</span>
          <div>
            <h2>Published inputs are required</h2>
            <p>
              Import a published catalog and create a published AI-system version in
              this project before running the playground.
            </p>
          </div>
        </section>
      ) : (
        <form className="assistant-form" onSubmit={submit}>
          <div className="assistant-select-grid">
            <label>
              <span>Catalog version</span>
              <select value={catalogVersionId} onChange={(event) => setCatalogVersionId(event.target.value)}>
                {catalogOptions.map(({ catalog, version }) => (
                  <option key={version.id} value={version.id}>{catalog.name} · {version.version} · {version.item_count.toLocaleString()} products</option>
                ))}
              </select>
            </label>
            <label>
              <span>AI system version</span>
              <select value={systemVersionId} onChange={(event) => setSystemVersionId(event.target.value)}>
                {systemOptions.map(({ system, version }) => (
                  <option key={version.id} value={version.id}>{system.name} · {version.version} · {system.system_type}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="assistant-query-field">
            <span>Shopping question</span>
            <textarea
              value={query}
              maxLength={500}
              required
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ask for products with clear constraints…"
            />
          </label>
          <div className="assistant-examples" aria-label="Example questions">
            {EXAMPLES.map((example) => (
              <button type="button" key={example} onClick={() => setQuery(example)}>{example}</button>
            ))}
          </div>
          <button className="primary-button assistant-run-button" disabled={pending || !query.trim()}>
            {pending ? "Retrieving verified evidence…" : "Run grounded retrieval"}
          </button>
        </form>
      )}

      {error ? <div className="form-error" role="alert">{error}</div> : null}

      {result ? (
        <section className="assistant-result" aria-live="polite">
          <div className="assistant-answer-panel">
            <header>
              <div><p className="eyebrow">GROUNDED RESPONSE</p><h2>Assistant answer</h2></div>
              <span>{result.latency_ms.toFixed(2)} ms</span>
            </header>
            <p className="assistant-answer">{result.answer}</p>
            {result.missing_information.length > 0 ? (
              <div className="assistant-abstention"><strong>Missing evidence</strong>{result.missing_information.map((item) => <span key={item}>{item}</span>)}</div>
            ) : null}
            <div className="assistant-filter-row">
              {activeFilters(result.applied_filters).map(([key, value]) => <span key={key}><strong>{key}</strong>{value}</span>)}
            </div>
            <div className="assistant-product-grid">
              {result.products.map((product) => (
                <article className="assistant-product-card" key={product.product_id}>
                  <div className="assistant-product-rank">#{product.rank}</div>
                  <div>
                    <p>{product.category}{product.brand ? ` · ${product.brand}` : ""}</p>
                    <h3>{product.title}</h3>
                    <span>{product.description ?? "No description provided"}</span>
                  </div>
                  <dl>
                    <div><dt>Price</dt><dd>{product.price ? `${product.currency} ${product.price}` : "Not available"}</dd></div>
                    <div><dt>Availability</dt><dd>{product.availability.replaceAll("_", " ")}</dd></div>
                    <div><dt>Score</dt><dd>{product.score.toFixed(3)}</dd></div>
                  </dl>
                  <footer><strong>[{product.product_id}]</strong><span>Catalog {product.citation.source_version}</span></footer>
                </article>
              ))}
            </div>
          </div>

          <aside className="assistant-evidence-panel">
            <div><p className="eyebrow">EVIDENCE TRACE</p><h2>Why this answer?</h2></div>
            <dl className="assistant-trace-meta">
              <div><dt>Mode</dt><dd>{result.mode.replaceAll("_", " ")}</dd></div>
              <div><dt>Generator</dt><dd>{result.generation_provider}</dd></div>
              <div><dt>AI system</dt><dd>{result.system.name} · {result.system.version}</dd></div>
              <div><dt>System hash</dt><dd>{compactHash(result.system.content_hash)}</dd></div>
              <div><dt>Catalog</dt><dd>{result.catalog.name} · {result.catalog.version}</dd></div>
              <div><dt>Catalog hash</dt><dd>{compactHash(result.catalog.content_hash)}</dd></div>
            </dl>
            <div className="assistant-candidate-counts">
              <div><strong>{result.retrieved_candidate_ids.length}</strong><span>Retrieved</span></div>
              <div><strong>{result.filtered_candidate_ids.length}</strong><span>After filters</span></div>
              <div><strong>{result.products.length}</strong><span>Returned</span></div>
            </div>
            <div className="assistant-citations">
              <h3>Citations</h3>
              {result.citations.length === 0 ? <p>No source supported a recommendation.</p> : result.citations.map((citation) => (
                <article key={`${citation.source_id}-${citation.claim}`}>
                  <strong>[{citation.source_id}]</strong>
                  <p>{citation.claim}</p>
                  <span>Immutable source version {citation.source_version}</span>
                </article>
              ))}
            </div>
          </aside>
        </section>
      ) : null}
    </div>
  );
}
