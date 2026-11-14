// Tyypit vastaavat bouncer.api.app-vastauksia (MVP). OpenAPI-generointi (päätös 006) myöhemmin.

export type Label = "bad_bot" | "good_bot" | "human" | "uncertain";

export interface Summary {
  updated_at: string | null;
  synthetic: boolean;
  source: string | null;
  n_sessions: number;
  by_label: Record<Label, number>;
  n_campaigns: number;
  ingest: Record<string, unknown>;
}

export interface SessionRow {
  id: string;
  ip: string;
  user_agent: string;
  started_at: string;
  ended_at: string;
  n_requests: number;
  label: Label;
  score: number | null;
  reason: string;
  campaign_id: string | null;
  sim_class: string | null;
}

export interface Campaign {
  id: string;
  kind: string;
  session_ids: string[];
  reasons: string[];
  size: number;
  labels?: Partial<Record<Label, number>>;
}

export interface SessionDetail extends SessionRow {
  verdict: {
    label: Label;
    score: number;
    reasons: string[];
    model_version: string;
    explanation?: string;
    verified_bot?: boolean | null;
    asn_type?: string;
  };
  campaign: Campaign | null;
  requests: { ts: string; method: string; path: string; status: number; username: string | null }[];
}

export interface MetricsResponse {
  metrics: Record<string, unknown> & { stub?: boolean; human_fpr?: number | null };
  stub: boolean;
  synthetic_data: boolean;
  known_weaknesses: string[];
  ingest: Record<string, unknown>;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  summary: () => get<Summary>("/api/summary"),
  sessions: () => get<SessionRow[]>("/api/sessions"),
  session: (id: string) => get<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  campaigns: () => get<Campaign[]>("/api/campaigns"),
  metrics: () => get<MetricsResponse>("/api/metrics"),
};

export const LABEL_TEXT: Record<Label, string> = {
  bad_bot: "Haitallinen botti",
  good_bot: "Hyvä botti",
  human: "Ihminen",
  uncertain: "Epävarma",
};
