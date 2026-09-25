export interface CatalogSummary {
  id: string;
  organization_id: string;
  project_id: string;
  external_id: string | null;
  name: string;
  created_at: string;
}

export interface CatalogVersionSummary {
  id: string;
  organization_id: string;
  catalog_id: string;
  version: string;
  status: string;
  content_hash: string | null;
  artifact_hash: string | null;
  item_count: number;
  provenance: Record<string, unknown>;
  created_at: string;
}

export interface CatalogWithVersions extends CatalogSummary {
  versions: CatalogVersionSummary[];
}

export interface CatalogImportResult {
  resource_id: string;
  version_id: string;
  external_id: string;
  version: string;
  created: boolean;
  item_count: number;
  content_hash: string;
  artifact_hash: string;
}
