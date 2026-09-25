export interface AISystemVersionSummary {
  id: string;
  organization_id: string;
  ai_system_id: string;
  version: string;
  configuration: Record<string, unknown>;
  capabilities: Record<string, boolean>;
  status: string;
  content_hash: string;
  created_at: string;
}

export interface AISystemSummary {
  id: string;
  organization_id: string;
  project_id: string;
  name: string;
  system_type: string;
  provider: string;
  description: string | null;
  status: string;
  created_at: string;
}

export interface AISystemWithVersions extends AISystemSummary {
  versions: AISystemVersionSummary[];
}

export interface AssistantCitation {
  claim: string;
  source_id: string;
  source_version: string;
}

export interface AssistantProductEvidence {
  product_id: string;
  title: string;
  description: string | null;
  category: string;
  brand: string | null;
  color: string | null;
  price: string | null;
  currency: string;
  availability: string;
  rank: number;
  score: number;
  score_breakdown: Record<string, number>;
  citation: AssistantCitation;
}

export interface AssistantPlaygroundResponse {
  answer: string;
  mode: "DETERMINISTIC_REFERENCE";
  generation_provider: "DISABLED";
  system: {
    id: string;
    version_id: string;
    name: string;
    version: string;
    system_type: string;
    provider: string;
    capabilities: Record<string, unknown>;
    content_hash: string;
  };
  catalog: {
    id: string;
    version_id: string;
    name: string;
    external_id: string | null;
    version: string;
    content_hash: string | null;
  };
  interpreted_query: Record<string, unknown> | null;
  applied_filters: Record<string, unknown> | null;
  retrieved_candidate_ids: string[];
  filtered_candidate_ids: string[];
  products: AssistantProductEvidence[];
  citations: AssistantCitation[];
  missing_information: string[];
  latency_ms: number;
}
