import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { api } from "@/api";
import { ListSkeleton } from "@/components/Skeletons";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const fmt = (x: unknown) => (typeof x === "number" ? `${(x * 100).toFixed(1)} %` : "—");

function Tile({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <Card className="rise gap-2">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
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
  if (error) return <p className="text-destructive">API ei vastaa: {String(error)}</p>;
  if (!m) return <ListSkeleton rows={4} />;
  // Rehellisyys (AGENTS.md §7): stub-tilassa lukuja ei näytetä eikä keksitä.
  const hide = m.stub;
  return (
    <div className="flex flex-col gap-4">
      {(m.stub || m.synthetic_data) && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
          <p>
            {m.stub
              ? "models/metrics.json on stub: oikeaa labeloitua liikennettä ei vielä ole. Lukuja ei näytetä eikä keksitä."
              : "Luvut on laskettu synteettisellä datalla: niillä ei ole todistusarvoa."}
          </p>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <Tile
          title="Ihmisten väärät hälytykset (FPR)"
          value={hide ? "—" : fmt(m.metrics.human_fpr)}
          note={`95 % yläraja ${hide ? "—" : fmt(m.metrics["human_fpr_ci95_upper"])} · tavoite alle 1 %`}
        />
        <Tile title="Epävarmojen osuus" value={hide ? "—" : fmt(m.metrics["uncertain_share"])} />
        <Tile title="Malli" value={String(m.metrics["model_version"] ?? "—")} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Mitä emme tunnista</CardTitle>
          <CardDescription>Tunnetut heikkoudet — kirjataan, ei piiloteta</CardDescription>
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
        <summary className="cursor-pointer">Ingest-tila</summary>
        <pre className="mt-2 overflow-x-auto rounded-md border bg-muted/30 p-3">{JSON.stringify(m.ingest, null, 2)}</pre>
      </details>
    </div>
  );
}
