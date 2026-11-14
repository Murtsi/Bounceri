import { useQuery } from "@tanstack/react-query";
import { CircleHelp, Cpu, EyeOff, type LucideIcon, TriangleAlert, UserX } from "lucide-react";
import { api } from "@/api";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { ListSkeleton } from "@/components/Skeletons";
import { CardHeading, CardIcon } from "@/components/CardIcon";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

const fmt = (x: unknown) => (typeof x === "number" ? `${(x * 100).toFixed(1)}%` : "—");

function Tile({ Icon, title, value, note }: { Icon: LucideIcon; title: string; value: string; note?: string }) {
  return (
    <Card className="rise gap-2">
      <CardHeader>
        <div className="flex items-center gap-3">
          <CardIcon Icon={Icon} />
          <CardDescription>{title}</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
        {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
      </CardContent>
    </Card>
  );
}

export default function Metrics() {
  const { data: m, error } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!m) return <ListSkeleton rows={4} />;
  // Rehellisyys (AGENTS.md §7): stub-tilassa lukuja ei näytetä eikä keksitä.
  const hide = m.stub;
  return (
    <div className="flex flex-col gap-4">
      {(m.stub || m.synthetic_data) && (
        <div
          role="status"
          className="glass flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
          <p>
            {m.stub
              ? "models/metrics.json is a stub: there is no real labelled traffic yet. No numbers are shown or invented."
              : SYNTHETIC_DATA_NOTICE}
          </p>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <Tile
          Icon={UserX}
          title="False alarms on humans (FPR)"
          value={hide ? "—" : fmt(m.metrics.human_fpr)}
          note={`95% upper bound ${hide ? "—" : fmt(m.metrics["human_fpr_ci95_upper"])} · target under 1%`}
        />
        <Tile Icon={CircleHelp} title="Uncertain share" value={hide ? "—" : fmt(m.metrics["uncertain_share"])} />
        <Tile Icon={Cpu} title="Model" value={String(m.metrics["model_version"] ?? "—")} />
      </div>
      <Card>
        <CardHeader>
          <CardHeading Icon={EyeOff} title="What we don’t catch" description="Known weaknesses — written down, never hidden" />
        </CardHeader>
        <CardContent>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed">
            {m.known_weaknesses.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Ingest status</summary>
        <pre className="mt-2 overflow-x-auto rounded-md border bg-muted/30 p-3">{JSON.stringify(m.ingest, null, 2)}</pre>
      </details>
    </div>
  );
}
