export interface Capability {
  enabled?: boolean;
  implemented?: boolean;
  reason?: string;
}

export interface Capabilities {
  modules?: Record<string, Capability> | (Capability & { id?: string; module?: string; key?: string })[];
  providers?: { mode?: string; decision_model?: ProviderCapability; reviewer?: ProviderCapability };
  decision_model?: ProviderCapability;
  reviewer?: ProviderCapability;
}

export interface ProviderCapability {
  provider?: string;
  model?: string | null;
  role?: string;
  available?: boolean;
}

export interface Assessment {
  id: string;
  stage?: string;
  kind?: string;
  created_at?: string;
  payload?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

export interface LocalAssessment {
  id?: string;
  kind?: string;
  created_at?: string;
  label?: string;
  score?: number | null;
  model_version?: string;
  reasons?: unknown[];
  evidence_ids?: string[];
  limitations?: string[];
}

export interface Investigation {
  id: string;
  module?: string;
  title?: string;
  source?: { kind?: string; synthetic?: boolean };
  created_at?: string;
  evidence_version?: string | number;
  evidence_hash?: string;
  complete?: boolean;
  review_eligibility?: { eligible?: boolean; reason?: string | null };
  missing_information?: string[];
  evidence?: { id: string; kind?: string; data?: Record<string, unknown> }[];
  local_assessment?: LocalAssessment | null;
  review?: {
    status?: string;
    job_id?: string | null;
    result?: Record<string, unknown> | null;
    reason?: string;
  };
}

export interface EnforcementPolicy {
  id: string;
  case_id?: string;
  actor_id?: string;
  scope?: string;
  action?: string;
  approval_basis?: string;
  status?: string;
  evidence_version?: number;
  evidence_hash?: string;
  created_at?: number;
  expires_at?: number;
  revoked_at?: number | null;
  expired_at?: number | null;
  affected_requests?: number;
  allowed_requests?: number;
  audit?: { event?: string; at?: number; details?: Record<string, unknown> }[];
}

export interface Usage {
  limit_usd?: number;
  spent_usd?: number;
  reserved_usd?: number;
  available_usd?: number;
  executions?: number;
  requests?: number;
  max_executions?: number;
  max_requests?: number;
  paid_review_enabled?: boolean;
  execution_halted?: boolean;
  halt_reason?: string;
}

export interface EvaluationMetric {
  numerator?: number;
  denominator?: number;
  value?: number | null;
  ci95_lower?: number | null;
  ci95_upper?: number | null;
}

export interface EvaluationResponse {
  schema_version?: number;
  available: boolean;
  reason?: string;
  synthetic?: boolean;
  dataset?: { id?: string; split?: string; n_sessions?: number; n_runs?: number; n_known?: number; n_unknown?: number };
  detector?: { model_version?: string; freeze_commit?: string; source_code_sha256?: Record<string, string> };
  metrics?: {
    bad_bot_precision?: EvaluationMetric;
    human_false_positive_rate?: EvaluationMetric;
    uncertain_share?: EvaluationMetric;
  };
  limitations?: string[];
  unavailable?: string[];
}

class ApiReadError extends Error {
  status: number;
  constructor(status: number) {
    super(`Service returned HTTP ${status}.`);
    this.status = status;
  }
}

async function get(path: string): Promise<unknown> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiReadError(response.status);
  try {
    return await response.json();
  } catch {
    throw new Error("Service did not return a readable record.");
  }
}

function record<T>(value: unknown): T {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Service returned an unexpected record.");
  return value as T;
}

async function list<T>(path: string): Promise<T[]> {
  const value = await get(path);
  const items = Array.isArray(value) ? value : (value as { items?: unknown } | null)?.items;
  if (!Array.isArray(items)) throw new Error("Service returned an unexpected list.");
  return items as T[];
}

// Public inspection is GET-only. Case creation, paid review and enforcement require
// an authenticated operator; no credentials or write actions belong in this bundle.
export type InvestigationOrigin = "all" | "real" | "synthetic";

export const investigationApi = {
  capabilities: async () => record<Capabilities>(await get("/api/capabilities")),
  investigations: (origin: InvestigationOrigin = "all", offset = 0) =>
    list<Investigation>(`/api/investigations?limit=100&offset=${offset}&origin=${origin}`),
  investigation: async (id: string) =>
    record<Investigation>(await get(`/api/investigations/${encodeURIComponent(id)}`)),
  assessments: (id: string) => list<Assessment>(`/api/investigations/${encodeURIComponent(id)}/assessments`),
  enforcements: (id: string) => list<EnforcementPolicy>(`/api/investigations/${encodeURIComponent(id)}/enforcements`),
  usage: async () => record<Usage>(await get("/api/usage")),
  evaluation: async (): Promise<EvaluationResponse> => {
    try {
      return record<EvaluationResponse>(await get("/api/evaluation"));
    } catch (error) {
      if (error instanceof ApiReadError && error.status === 404)
        return { available: false, reason: "Evaluation has not been published." };
      throw error;
    }
  },
};
