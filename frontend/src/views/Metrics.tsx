import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { api } from "@/api";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { ListSkeleton } from "@/components/Skeletons";
import ReplyResearchPreview from "@/components/ReplyResearchPreview";

const fmt = (x: unknown) => (typeof x === "number" ? `${(x * 100).toFixed(1)}%` : "—");

/** Yksi tunnusluku: otsikko, arvo, huomautus. Kolme rinnakkain yhdessä rivissä. */
function Figure({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <div className="metric-figure">
      <dt>{title}</dt>
      <dd>
        <span className="metric-value">{value}</span>
        {note && <span className="metric-note">{note}</span>}
      </dd>
    </div>
  );
}

export default function Metrics() {
  const { data: m, error } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!m) return <ListSkeleton rows={4} />;
  // Rehellisyys (AGENTS.md §7): stub-tilassa lukuja ei näytetä eikä keksitä.
  const hide = m.stub;
  return (
    <div className="flex flex-col gap-8">
      {(m.stub || m.synthetic_data) && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-[rgba(250,178,25,0.22)] bg-[rgba(250,178,25,0.05)] px-4 py-3 text-sm"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
          <p>
            {m.stub
              ? "models/metrics.json is a stub: native production quality is unmeasured. No native quality metrics are shown or invented."
              : SYNTHETIC_DATA_NOTICE}
          </p>
        </div>
      )}
      <dl className="metric-strip">
        <Figure
          title="False alarms on humans (FPR)"
          value={hide ? "—" : fmt(m.metrics.human_fpr)}
          note={`95% upper bound ${hide ? "—" : fmt(m.metrics["human_fpr_ci95_upper"])} · target under 1%`}
        />
        <Figure title="Uncertain share" value={hide ? "—" : fmt(m.metrics["uncertain_share"])} />
        <Figure title="Model" value={String(m.metrics["model_version"] ?? "—")} />
      </dl>
      <section className="overview-section" aria-labelledby="weak-title">
        <header className="section-head">
          <h2 id="weak-title">What we don’t catch</h2>
          <p>Known weaknesses — written down, never hidden</p>
        </header>
        <ol className="weakness-list">
          {m.known_weaknesses.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ol>
      </section>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Ingest status</summary>
        <pre className="mt-2 overflow-x-auto rounded-md border bg-muted/30 p-3">{JSON.stringify(m.ingest, null, 2)}</pre>
      </details>
      <ReplyResearchPreview />
    </div>
  );
}
