import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  investigationApi,
  type Assessment,
  type Capabilities,
  type Investigation,
  type LocalAssessment,
} from "./investigationsApi";
import {
  assessmentStage,
  capabilityState,
  dateTime,
  findingLabel,
  formatScore,
  reviewState,
  sourceState,
  type Tone,
} from "./investigationPresentation";

const TONES: Record<Tone, string> = {
  neutral: "border-zinc-200 bg-zinc-100 text-zinc-700",
  info: "border-blue-200 bg-blue-50 text-blue-800",
  warning: "border-amber-300 bg-amber-50 text-amber-900",
  danger: "border-red-200 bg-red-50 text-red-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

function ErrorState({ title, error, retry }: { title: string; error: unknown; retry: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-semibold">{title}</p>
      <p className="mt-1">
        {error instanceof Error ? error.message : "The service could not be reached."} This is not a no-findings result.
      </p>
      <button
        className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 font-semibold hover:bg-red-100"
        onClick={retry}
      >
        Try again
      </button>
    </div>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="space-y-3 py-3">
      <p className="text-sm text-zinc-600">{label}</p>
      <div className="h-3 w-2/3 rounded bg-zinc-200" />
      <div className="h-3 w-1/2 rounded bg-zinc-100" />
    </div>
  );
}

function moduleCapability(data: Capabilities | undefined, id: string) {
  const modules = data?.modules;
  if (Array.isArray(modules))
    return modules.find(
      (item) =>
        (item.id ?? item.module ?? item.key) === id ||
        (id === "clean_traffic" && (item.id ?? item.module ?? item.key) === "clean_the_traffic"),
    );
  return modules?.[id] ?? (id === "clean_traffic" ? modules?.clean_the_traffic : undefined);
}

function CapabilitiesPanel() {
  const query = useQuery({
    queryKey: ["capabilities"],
    queryFn: investigationApi.capabilities,
    retry: false,
    refetchInterval: 30_000,
  });
  const modules = [
    ["clean_traffic", "Clean the traffic", "HTTP activity, session patterns and coordinated login attempts."],
    ["spot_the_swarm", "Spot the swarm", "Social coordination · later module"],
    ["name_the_technique", "Name the technique", "Text manipulation techniques · later module"],
    ["trust_the_source", "Trust the source", "Source provenance · optional later module"],
  ];
  return (
    <section aria-labelledby="modules-title" className="rounded-xl border border-zinc-200 bg-white">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h2 id="modules-title" className="font-semibold">
          Investigation modules
        </h2>
        <p className="mt-1 text-sm text-zinc-600">Traffic first. Each module has its own evidence and limits.</p>
      </div>
      {query.error && (
        <div className="p-4">
          <ErrorState title="Capability status unavailable" error={query.error} retry={() => void query.refetch()} />
        </div>
      )}
      <ul className="divide-y divide-zinc-100">
        {modules.map(([id, name, description]) => {
          const state = capabilityState(id, moduleCapability(query.data, id));
          return (
            <li key={id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold">{name}</p>
                <p className="mt-0.5 text-xs text-zinc-600">{description}</p>
              </div>
              <Badge tone={state.enabled ? "info" : "neutral"}>
                {query.isPending && id === "clean_traffic" ? "Checking status…" : state.label}
              </Badge>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function UsagePanel() {
  const query = useQuery({
    queryKey: ["usage"],
    queryFn: investigationApi.usage,
    retry: false,
    refetchInterval: 30_000,
  });
  const usage = query.data;
  const money = (value: unknown) =>
    typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(2)}` : "Not reported";
  const count = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : "—");
  return (
    <section aria-labelledby="usage-title" className="rounded-xl border border-zinc-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="usage-title" className="font-semibold">
          Model review budget
        </h2>
        <Badge tone={usage?.paid_review_enabled === true ? "info" : "neutral"}>
          {usage?.paid_review_enabled === true
            ? "Operator access only"
            : usage?.paid_review_enabled === false
              ? "Paid review disabled"
              : "Status unavailable"}
        </Badge>
      </div>
      {query.isPending && <Loading label="Loading usage…" />}
      {query.error && (
        <div className="mt-3">
          <ErrorState title="Usage unavailable" error={query.error} retry={() => void query.refetch()} />
        </div>
      )}
      {usage && (
        <>
          <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4 text-sm">
            {(
              [
                ["Spent", usage.spent_usd],
                ["Reserved", usage.reserved_usd],
                ["Available", usage.available_usd],
                ["Total limit", usage.limit_usd],
              ] as const
            ).map(([name, value]) => (
              <div key={name}>
                <dt className="text-xs text-zinc-600">{name}</dt>
                <dd className="mt-1 font-mono font-semibold tabular-nums">{money(value)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 border-t border-zinc-100 pt-3 text-xs leading-relaxed text-zinc-600">
            Executions {count(usage.executions)} / {count(usage.max_executions)} · Requests {count(usage.requests)} /{" "}
            {count(usage.max_requests)}
            <br />
            Reserved funds are not confirmed spend.
          </p>
        </>
      )}
      <p className="mt-3 text-xs leading-relaxed text-zinc-600">
        Public access is read-only. Model reviews and enforcement require an authorised operator.
      </p>
    </section>
  );
}

function RecordFields({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="divide-y divide-zinc-100 text-sm">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="grid gap-1 py-2 sm:grid-cols-[minmax(8rem,1fr)_2fr] sm:gap-4">
          <dt className="break-words text-zinc-600">{key.replaceAll("_", " ")}</dt>
          <dd className="min-w-0 break-words whitespace-pre-wrap font-mono text-xs leading-relaxed">
            {Array.isArray(value) && value.every((item) => typeof item === "string" || typeof item === "number")
              ? value.join(", ")
              : typeof value === "object" && value !== null
                ? JSON.stringify(value, null, 2)
                : value == null
                  ? "Not reported"
                  : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function EvidenceLinks({ ids, onEvidence }: { ids?: unknown; onEvidence: (id: string) => void }) {
  if (!Array.isArray(ids) || ids.length === 0)
    return <p className="mt-3 text-xs text-zinc-600">No evidence references supplied.</p>;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <span className="text-zinc-600">Evidence</span>
      {ids
        .filter((id): id is string => typeof id === "string")
        .map((id) => (
          <a
            key={id}
            className="break-all rounded border border-zinc-200 px-2 py-1 font-mono text-blue-800 underline decoration-blue-200 underline-offset-2 hover:bg-blue-50"
            href={`#evidence-${encodeURIComponent(id)}`}
            onClick={() => onEvidence(id)}
          >
            {id}
          </a>
        ))}
    </div>
  );
}

function LocalFinding({
  assessment,
  onEvidence,
}: {
  assessment?: LocalAssessment | null;
  onEvidence: (id: string) => void;
}) {
  if (!assessment)
    return (
      <p className="text-sm text-zinc-600">
        No local assessment has been supplied. This does not establish that the activity is benign.
      </p>
    );
  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{findingLabel(assessment.label)}</p>
          <p className="mt-1 text-xs text-zinc-600">Detector score: {formatScore(assessment.score)}</p>
        </div>
        <Badge>Local detector</Badge>
      </div>
      <p className="mt-3 text-xs text-zinc-600">
        {assessment.model_version ?? "Model version not reported"} · {dateTime(assessment.created_at)}
      </p>
      {Array.isArray(assessment.reasons) && assessment.reasons.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 leading-relaxed">
          {assessment.reasons.map((reason, index) => (
            <li key={index}>{typeof reason === "string" ? reason : JSON.stringify(reason)}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-zinc-600">No supporting reasons supplied.</p>
      )}
      <EvidenceLinks ids={assessment.evidence_ids} onEvidence={onEvidence} />
      <p className="mt-3 text-xs leading-relaxed text-zinc-600">
        A detector score is not verified human identity or proof of malicious intent.
      </p>
    </div>
  );
}

function AssessmentRecord({ assessment, onEvidence }: { assessment: Assessment; onEvidence: (id: string) => void }) {
  const payload = assessment.payload;
  return (
    <li className="border-t border-zinc-200 py-4 first:border-0 first:pt-0">
      <p className="text-xs text-zinc-600">{dateTime(assessment.created_at)}</p>
      <p className="mt-1 break-all font-mono text-xs text-zinc-600">{assessment.id}</p>
      {payload && typeof payload === "object" ? (
        <>
          <RecordFields data={payload} />
          <EvidenceLinks ids={payload.evidence_ids ?? payload.supporting_evidence_ids} onEvidence={onEvidence} />
        </>
      ) : (
        <p className="mt-2 text-sm text-zinc-600">No assessment payload supplied.</p>
      )}
    </li>
  );
}

function AssessmentHistory({
  id,
  local,
  onEvidence,
}: {
  id: string;
  local?: LocalAssessment | null;
  onEvidence: (id: string) => void;
}) {
  const query = useQuery({
    queryKey: ["assessments", id],
    queryFn: () => investigationApi.assessments(id),
    retry: false,
    refetchInterval: 5_000,
  });
  const stages = [
    ["local", "Local detector", "Baseline findings"],
    ["decision_model", "Microsoft Decision-1", "Optional decision assessment"],
    ["reviewer", "Featherless reviewer", "Optional advisory recommendation"],
  ];
  const other = query.data?.filter((item) => !stages.some(([kind]) => assessmentStage(item) === kind)) ?? [];
  return (
    <section aria-labelledby="history-title" className="space-y-4">
      <div>
        <h3 id="history-title" className="font-semibold">
          Assessment history
        </h3>
        <p className="mt-1 text-sm text-zinc-600">
          Stages are separate records. Model agreement is not independent corroboration.
        </p>
      </div>
      {query.isPending && <Loading label="Loading assessment history…" />}
      {query.error && (
        <ErrorState title="History could not be loaded" error={query.error} retry={() => void query.refetch()} />
      )}
      {query.data && (
        <div className="grid divide-y divide-zinc-200 rounded-lg border border-zinc-200 md:grid-cols-3 md:divide-x md:divide-y-0">
          {stages.map(([kind, title, subtitle]) => {
            const records = query.data.filter((item) => assessmentStage(item) === kind);
            return (
              <div key={kind} className="min-w-0 p-4">
                <h4 className="text-sm font-semibold">{title}</h4>
                <p className="mt-1 text-xs text-zinc-600">{subtitle}</p>
                <div className="mt-4">
                  {records.length > 0 ? (
                    <ul>
                      {records.map((record) => (
                        <AssessmentRecord key={record.id} assessment={record} onEvidence={onEvidence} />
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm leading-relaxed text-zinc-600">
                      {kind === "local" && local
                        ? "Current local assessment is shown above. No history revision supplied."
                        : "No recorded assessment."}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {other.length > 0 && (
        <details className="rounded-lg border border-zinc-200 p-4">
          <summary className="cursor-pointer text-sm font-medium">Other assessment stages ({other.length})</summary>
          <ul className="mt-4">
            {other.map((record) => (
              <AssessmentRecord key={record.id} assessment={record} onEvidence={onEvidence} />
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function EnforcementPanel({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["enforcements", id],
    queryFn: () => investigationApi.enforcements(id),
    retry: false,
    refetchInterval: 2_000,
  });
  const timestamp = (value?: number | null) =>
    typeof value === "number" && Number.isFinite(value) && Math.abs(value) < 8_640_000_000_000
      ? dateTime(new Date(value * 1000).toISOString())
      : "Not reported";
  const count = (value?: number) =>
    typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : "Not reported";
  return (
    <section className="border-t border-zinc-200 pt-5" aria-labelledby="enforcement-title">
      <h3 id="enforcement-title" className="font-semibold">
        Enforcement
      </h3>
      <p className="mt-2 text-xs leading-relaxed text-zinc-600">
        These policies apply only to registered demo actors. Assessments are advisory; applying or reversing an action
        requires an authorised operator.
      </p>
      {query.isPending && <Loading label="Loading enforcement policies…" />}
      {query.error && (
        <div className="mt-3">
          <ErrorState
            title="Enforcement status could not be loaded"
            error={query.error}
            retry={() => void query.refetch()}
          />
        </div>
      )}
      {!query.error &&
        query.data &&
        (query.data.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-600">No enforcement policies recorded for this investigation.</p>
        ) : (
          <ul className="mt-4 divide-y divide-zinc-200">
            {query.data.map((policy) => {
              const status = (
                {
                  active: { label: "Active", tone: "info" },
                  revoked: { label: "Revoked", tone: "neutral" },
                  expired: { label: "Expired", tone: "neutral" },
                } as Record<string, { label: string; tone: Tone }>
              )[policy.status ?? ""] ?? { label: "Status unavailable", tone: "warning" as Tone };
              return (
                <li key={policy.id} className="min-w-0 space-y-3 py-4 first:pt-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold">
                      {policy.action === "rate_limit"
                        ? "Rate limit"
                        : policy.action === "temporary_block"
                          ? "Temporary block"
                          : (policy.action ?? "Action not reported")}
                    </p>
                    <Badge tone={status.tone}>{status.label}</Badge>
                  </div>
                  <p className="break-all font-mono text-xs text-zinc-600">{policy.id}</p>
                  <p className="text-sm">Controlled demo actor: {policy.actor_id ?? "Not reported"}</p>
                  <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm tabular-nums">
                    <p>Affected requests: {count(policy.affected_requests)}</p>
                    <p>Allowed requests: {count(policy.allowed_requests)}</p>
                  </div>
                  <dl className="grid gap-3 text-xs sm:grid-cols-2">
                    <div>
                      <dt className="text-zinc-600">Approved</dt>
                      <dd className="mt-1">{timestamp(policy.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-zinc-600">Expires</dt>
                      <dd className="mt-1">{timestamp(policy.expires_at)}</dd>
                    </div>
                    {policy.revoked_at != null && (
                      <div>
                        <dt className="text-zinc-600">Revoked at</dt>
                        <dd className="mt-1">{timestamp(policy.revoked_at)}</dd>
                      </div>
                    )}
                    {policy.expired_at != null && (
                      <div>
                        <dt className="text-zinc-600">Expired at</dt>
                        <dd className="mt-1">{timestamp(policy.expired_at)}</dd>
                      </div>
                    )}
                  </dl>
                  <details>
                    <summary className="cursor-pointer text-xs font-medium text-blue-800">
                      Policy scope and audit record
                    </summary>
                    <RecordFields
                      data={{
                        scope: policy.scope,
                        evidence_version: policy.evidence_version,
                        evidence_hash: policy.evidence_hash,
                        audit: policy.audit,
                      }}
                    />
                  </details>
                </li>
              );
            })}
          </ul>
        ))}
    </section>
  );
}

function InvestigationDetail({ id, onClose, goTraffic }: { id: string; onClose: () => void; goTraffic: () => void }) {
  const query = useQuery({
    queryKey: ["investigation", id],
    queryFn: () => investigationApi.investigation(id),
    retry: false,
    refetchInterval: 5_000,
  });
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);
  const investigation = query.data;
  const origin = sourceState(investigation?.source);
  const review = reviewState(investigation?.review?.status);
  return (
    <section aria-labelledby="case-title" className="min-w-0 rounded-xl border border-zinc-200 bg-white p-4 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 id="case-title" className="text-lg font-semibold">
          Investigation record
        </h2>
        <button
          onClick={onClose}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-50"
        >
          Back to investigations
        </button>
      </div>
      {query.isPending && <Loading label="Loading investigation…" />}
      {query.error && (
        <ErrorState title="Investigation could not be loaded" error={query.error} retry={() => void query.refetch()} />
      )}
      {investigation && (
        <div className="space-y-7">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={origin.tone}>{origin.label}</Badge>
              <Badge>
                {investigation.module === "clean_the_traffic" || investigation.module === "clean_traffic"
                  ? "Clean the traffic"
                  : (investigation.module ?? "Module not reported")}
              </Badge>
            </div>
            <p className="mt-3 break-all font-mono text-xs text-zinc-600">{investigation.id}</p>
            <p className="mt-1 text-xs text-zinc-600">Created {dateTime(investigation.created_at)}</p>
            {origin.synthetic && (
              <p className="mt-3 rounded-md bg-amber-50 p-3 text-sm leading-relaxed text-amber-900">
                This is a synthetic example. Its findings do not establish performance on real traffic.
              </p>
            )}
          </div>
          <section aria-labelledby="finding-title">
            <h3 id="finding-title" className="mb-3 font-semibold">
              Local assessment
            </h3>
            <LocalFinding assessment={investigation.local_assessment} onEvidence={setExpandedEvidence} />
          </section>
          <section aria-labelledby="review-title" className="border-t border-zinc-200 pt-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id="review-title" className="font-semibold">
                Model review
              </h3>
              <Badge tone={review.tone}>{review.label}</Badge>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">{review.description}</p>
            {investigation.review?.job_id && (
              <p className="mt-2 break-all font-mono text-xs text-zinc-600">Job {investigation.review.job_id}</p>
            )}
            {investigation.review?.result && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium text-blue-800">Recorded review result</summary>
                <RecordFields data={investigation.review.result} />
              </details>
            )}
          </section>
          <section aria-labelledby="evidence-title" className="border-t border-zinc-200 pt-5">
            <h3 id="evidence-title" className="font-semibold">
              Evidence snapshot
            </h3>
            <dl className="mt-3 space-y-2 text-xs">
              <div className="flex flex-wrap gap-2">
                <dt className="text-zinc-600">Version</dt>
                <dd className="font-mono">{investigation.evidence_version ?? "Not reported"}</dd>
              </div>
              <div>
                <dt className="text-zinc-600">Snapshot hash</dt>
                <dd className="mt-1 break-all font-mono">{investigation.evidence_hash ?? "Not reported"}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs leading-relaxed text-zinc-600">
              The snapshot belongs to this investigation. Current traffic drilldowns can contain newer observations.
            </p>
            {Array.isArray(investigation.evidence) && investigation.evidence.length > 0 ? (
              <div className="mt-4 divide-y divide-zinc-200 rounded-lg border border-zinc-200">
                {investigation.evidence.map((item) => (
                  <details
                    key={item.id}
                    id={`evidence-${encodeURIComponent(item.id)}`}
                    open={expandedEvidence === item.id}
                    onToggle={(event) => {
                      const open = event.currentTarget.open;
                      setExpandedEvidence((current) => (open ? item.id : current === item.id ? null : current));
                    }}
                    className="scroll-mt-5 p-4"
                  >
                    <summary className="cursor-pointer break-all text-sm font-medium">
                      <span>{(item.kind ?? "Evidence").replaceAll("_", " ")}</span>
                      <span className="ml-2 font-mono text-xs text-zinc-600">{item.id}</span>
                    </summary>
                    <div className="mt-3">
                      {item.data && typeof item.data === "object" ? (
                        <RecordFields data={item.data} />
                      ) : (
                        <p className="text-sm text-zinc-600">No evidence data supplied.</p>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-zinc-600">
                No evidence items supplied. The evidence basis cannot be inspected.
              </p>
            )}
          </section>
          <AssessmentHistory id={id} local={investigation.local_assessment} onEvidence={setExpandedEvidence} />
          <EnforcementPanel id={id} />
          <button
            onClick={goTraffic}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold hover:bg-zinc-50"
          >
            Open current traffic overview →
          </button>
        </div>
      )}
    </section>
  );
}

function CaseRow({ investigation, onPick }: { investigation: Investigation; onPick: (id: string) => void }) {
  const origin = sourceState(investigation.source);
  const review = reviewState(investigation.review?.status);
  return (
    <li>
      <button
        onClick={() => onPick(investigation.id)}
        className="group flex w-full flex-wrap items-center justify-between gap-4 border-t border-zinc-200 px-5 py-5 text-left hover:bg-blue-50/50"
      >
        <div className="min-w-0 flex-1 basis-64">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold group-hover:text-blue-800">
              {investigation.title ??
                (investigation.module === "clean_the_traffic" || investigation.module === "clean_traffic"
                  ? "Traffic investigation"
                  : "Investigation")}
            </span>
            <Badge tone={origin.tone}>{origin.label}</Badge>
          </div>
          <p className="mt-2 break-all font-mono text-xs text-zinc-600">{investigation.id}</p>
          <p className="mt-1 text-xs text-zinc-600">{dateTime(investigation.created_at)}</p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-4">
          <div className="text-sm">
            <p className="font-medium">{findingLabel(investigation.local_assessment?.label)}</p>
            <p className="mt-1 text-xs text-zinc-600">Local assessment</p>
          </div>
          <Badge tone={review.tone}>{review.label}</Badge>
          <span aria-hidden="true" className="text-zinc-500">
            →
          </span>
        </div>
      </button>
    </li>
  );
}

export default function Investigations({ goTraffic }: { goTraffic: () => void }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const query = useQuery({
    queryKey: ["investigations"],
    queryFn: investigationApi.investigations,
    retry: false,
    refetchInterval: 5_000,
  });
  const cases = (query.data ?? []).filter(
    (item) =>
      filter === "all" ||
      (filter === "synthetic"
        ? item.source?.synthetic === true
        : item.source?.synthetic === false && item.source.kind === "monitored_traffic"),
  );
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Investigation workspace</h2>
        <p className="mt-1 max-w-prose text-sm text-zinc-600">
          Clean the traffic is the first module. Inspect source evidence, local findings and optional model review.
        </p>
      </div>
      {!picked && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(19rem,1fr)]">
          <CapabilitiesPanel />
          <UsagePanel />
        </div>
      )}
      {picked ? (
        <InvestigationDetail key={picked} id={picked} onClose={() => setPicked(null)} goTraffic={goTraffic} />
      ) : (
        <section
          aria-labelledby="investigations-title"
          className="overflow-hidden rounded-xl border border-zinc-200 bg-white"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
            <div>
              <h2 id="investigations-title" className="text-lg font-semibold">
                Investigations
              </h2>
              <p className="mt-1 text-sm text-zinc-600">
                Follow the evidence, local findings and each recorded review.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600">
              Source
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-zinc-900"
              >
                <option value="all">All origins</option>
                <option value="real">Real traffic</option>
                <option value="synthetic">Synthetic only</option>
              </select>
            </label>
          </div>
          {query.isPending && (
            <div className="px-5 pb-5">
              <Loading label="Loading investigations…" />
            </div>
          )}
          {query.error && (
            <div className="px-5 pb-5">
              <ErrorState
                title="Investigations could not be loaded"
                error={query.error}
                retry={() => void query.refetch()}
              />
            </div>
          )}
          {query.data && cases.length === 0 && (
            <div className="border-t border-zinc-200 px-5 py-8">
              <h3 className="text-sm font-semibold">
                {query.data.length === 0 ? "No investigations published yet" : "No investigations match this source"}
              </h3>
              <p className="mt-2 max-w-prose text-sm leading-relaxed text-zinc-600">
                {query.data.length === 0
                  ? "An operator can publish a sanitised traffic snapshot. An empty case list does not mean the monitored traffic is safe."
                  : "Choose another source to inspect the available cases."}
              </p>
              <button
                onClick={goTraffic}
                className="mt-4 text-sm font-semibold text-blue-800 underline underline-offset-4"
              >
                Inspect current traffic
              </button>
            </div>
          )}
          {cases.length > 0 && (
            <ul>
              {cases.map((investigation) => (
                <CaseRow key={investigation.id} investigation={investigation} onPick={setPicked} />
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
