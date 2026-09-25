"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { errorMessage } from "@/lib/api-errors";
import type { MembershipRole } from "@/lib/auth-types";
import type {
  CatalogImportResult,
  CatalogVersionSummary,
  CatalogWithVersions,
} from "@/lib/catalog-types";
import { can } from "@/lib/permissions";
import type { ProjectSummary } from "@/lib/project-types";

const MAX_BROWSER_FILE_BYTES = 20 * 1024 * 1024;

function shortHash(value: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "Not recorded";
}

function latestVersion(versions: CatalogVersionSummary[]): CatalogVersionSummary | null {
  return [...versions].sort(
    (left, right) =>
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  )[0] ?? null;
}

export function CatalogsConsole({
  organizationId,
  project,
  currentRole,
  catalogs,
}: {
  organizationId: string;
  project: ProjectSummary;
  currentRole: MembershipRole;
  catalogs: CatalogWithVersions[];
}): React.ReactElement {
  const router = useRouter();
  const canImport = can(currentRole, "manage_catalogs");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function importCatalog(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    setNotice(null);
    if (!selectedFile) {
      setError("Choose a catalog JSON file.");
      return;
    }
    if (selectedFile.size > MAX_BROWSER_FILE_BYTES) {
      setError("Catalog file must be 20 MB or smaller for browser import.");
      return;
    }

    setPending(true);
    try {
      let artifact: unknown;
      try {
        artifact = JSON.parse(await selectedFile.text());
      } catch {
        setError("Catalog file must contain valid UTF-8 JSON.");
        return;
      }
      if (!artifact || typeof artifact !== "object" || Array.isArray(artifact)) {
        setError("Catalog JSON root must be an object.");
        return;
      }

      const response = await fetch("/api/organization/catalog-imports", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "content-type": "application/json",
          "x-organization-id": organizationId,
        },
        body: JSON.stringify({ project_id: project.id, artifact }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(body, "Unable to import catalog."));
        return;
      }
      const result = body as CatalogImportResult;
      setNotice(
        result.created
          ? `${result.external_id} ${result.version} imported with ${result.item_count.toLocaleString()} products.`
          : `${result.external_id} ${result.version} already exists with identical immutable content.`,
      );
      setSelectedFile(null);
      form.reset();
      router.refresh();
    } catch {
      setError("Catalog import service is unavailable. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="catalog-layout">
      {canImport ? (
        <section className="catalog-import-panel" aria-labelledby="catalog-import-heading">
          <div>
            <p className="eyebrow">VALIDATED INGESTION</p>
            <h2 id="catalog-import-heading">Import catalog JSON</h2>
            <p>
              Browser imports are schema-validated, duplicate-checked, and
              published as immutable content-addressed versions.
            </p>
            <a href="/catalog-template.json" download>Download JSON template</a>
          </div>
          <form className="catalog-import-form" onSubmit={importCatalog}>
            <div className="catalog-file-field">
              <label htmlFor="catalog-file">Catalog artifact</label>
              <input
                id="catalog-file"
                name="catalog_file"
                type="file"
                accept="application/json,.json"
                required
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <small>{selectedFile ? `${selectedFile.name} · ${(selectedFile.size / 1024).toFixed(1)} KB` : "UTF-8 JSON · maximum 20 MB"}</small>
            </div>
            <button className="primary-button" disabled={pending || !selectedFile}>
              {pending ? "Validating & importing…" : "Import immutable version"}
            </button>
          </form>
        </section>
      ) : (
        <section className="project-readonly-note">
          <strong>Read-only catalog access</strong>
          <span>Your {currentRole} role can inspect versions but cannot import catalog content.</span>
        </section>
      )}

      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {notice ? <div className="form-success" role="status">{notice}</div> : null}

      <section className="catalog-section" aria-labelledby="catalog-list-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PROJECT INVENTORY</p>
            <h2 id="catalog-list-heading">Catalogs</h2>
          </div>
          <span>{catalogs.length} {catalogs.length === 1 ? "catalog" : "catalogs"}</span>
        </div>

        {catalogs.length === 0 ? (
          <div className="empty-project-state">
            <span className="empty-project-mark" aria-hidden="true">C</span>
            <strong>No catalogs in {project.name}</strong>
            <p>
              {canImport
                ? "Import a validated catalog artifact to create the first immutable version."
                : "A project resource manager has not imported a catalog yet."}
            </p>
          </div>
        ) : (
          <div className="catalog-list">
            {catalogs.map((catalog) => {
              const latest = latestVersion(catalog.versions);
              return (
                <article className="catalog-card" key={catalog.id}>
                  <header>
                    <div>
                      <span className="catalog-mark" aria-hidden="true">CAT</span>
                      <div>
                        <h3>{catalog.name}</h3>
                        <p>{catalog.external_id ?? "Metadata-only catalog"}</p>
                      </div>
                    </div>
                    <span className={`catalog-state ${latest ? "published" : "draft"}`}>
                      {latest?.status ?? "NO VERSION"}
                    </span>
                  </header>

                  {latest ? (
                    <>
                      <div className="catalog-version-hero">
                        <div><span>Latest version</span><strong>{latest.version}</strong></div>
                        <div><span>Products</span><strong>{latest.item_count.toLocaleString()}</strong></div>
                        <div><span>Published</span><strong>{new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(latest.created_at))}</strong></div>
                      </div>
                      <div className="catalog-quality-grid">
                        <div><i className="quality-pass" /><span>Schema validated</span></div>
                        <div><i className="quality-pass" /><span>Duplicate IDs rejected</span></div>
                        <div><i className="quality-pass" /><span>Immutable hash locked</span></div>
                      </div>
                      <dl className="catalog-hashes">
                        <div><dt>Content SHA-256</dt><dd title={latest.content_hash ?? undefined}>{shortHash(latest.content_hash)}</dd></div>
                        <div><dt>Artifact SHA-256</dt><dd title={latest.artifact_hash ?? undefined}>{shortHash(latest.artifact_hash)}</dd></div>
                      </dl>
                    </>
                  ) : (
                    <div className="catalog-no-version">
                      <strong>No published versions</strong>
                      <span>Import an artifact whose catalog ID matches this resource.</span>
                    </div>
                  )}

                  <details className="catalog-history">
                    <summary>Version history <span>{catalog.versions.length}</span></summary>
                    {catalog.versions.length === 0 ? (
                      <p>No immutable versions recorded.</p>
                    ) : (
                      <div>
                        {[...catalog.versions]
                          .sort((left, right) => right.version.localeCompare(left.version))
                          .map((version) => (
                            <div className="catalog-history-row" key={version.id}>
                              <strong>{version.version}</strong>
                              <span>{version.status}</span>
                              <span>{version.item_count.toLocaleString()} products</span>
                              <code title={version.content_hash ?? undefined}>{shortHash(version.content_hash)}</code>
                            </div>
                          ))}
                      </div>
                    )}
                  </details>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
