import { useQuery } from "@tanstack/react-query";
import { Rows3, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { api, LABEL_TEXT, type Label } from "@/api";
import { ActionBadge, LabelBadge } from "@/components/badges";
import { ListSkeleton } from "@/components/Skeletons";
import { CardHeading } from "@/components/CardIcon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const FILTERS: (Label | "all")[] = ["all", "bad_bot", "uncertain", "human", "good_bot"];

function SessionCard({ id, onClose }: { id: string; onClose: () => void }) {
  const { data: d } = useQuery({ queryKey: ["session", id], queryFn: () => api.session(id) });
  const ref = useRef<HTMLElement>(null);
  const loaded = !!d;
  useEffect(() => {
    // Kapealla näytöllä kortti on listan yläpuolella: vieritä se näkyviin.
    if (loaded && window.innerWidth < 1024) ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [id, loaded]);
  if (!d) return null;
  const v = d.verdict;
  return (
    <aside ref={ref} aria-label={`Session ${d.id}`} className="rise order-first flex w-full flex-col gap-4 lg:order-none lg:w-[420px] lg:shrink-0">
      <Card>
        <CardHeader>
          <CardDescription className="font-mono text-xs">session {d.id}</CardDescription>
          <CardTitle className="flex flex-wrap items-center gap-2">
            <LabelBadge label={v.label} />
            <ActionBadge action={d.action} />
          </CardTitle>
          <CardAction>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close session">
              <X />
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>P(bot)</span>
              <span className="tabular-nums text-foreground">{v.score.toFixed(2)}</span>
            </div>
            <div
              role="img"
              aria-label={`Bot probability ${v.score.toFixed(2)} on a 0–1 scale`}
              className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full rounded-full bg-foreground" style={{ width: `${Math.round(v.score * 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{v.model_version}</p>
          </div>
          <section>
            <h3 className="text-sm font-semibold">Why</h3>
            <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-5 text-sm leading-relaxed">
              {v.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ol>
          </section>
          {d.campaign && (
            <section className="rounded-lg bg-muted/60 p-3">
              <h3 className="text-sm font-semibold">Campaign</h3>
              <p className="mt-1 text-sm">{(d.campaign as { title?: string }).title ?? d.campaign.kind}</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {d.campaign.reasons.map((r) => (
                  <li key={r}>
                    <Badge variant="outline" className="max-w-full whitespace-normal break-words font-normal">
                      {r}
                    </Badge>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section>
            <h3 className="text-sm font-semibold">Session</h3>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted-foreground">IP</dt>
              <dd className="font-mono text-xs">{d.ip}</dd>
              <dt className="text-muted-foreground">DNS verification</dt>
              <dd>{v.verified_bot === true ? "verified bot" : v.verified_bot === false ? "failed" : "—"}</dd>
              <dt className="text-muted-foreground">User-Agent</dt>
              <dd className="break-all font-mono text-xs">{d.user_agent}</dd>
            </dl>
            <ul className="mt-3 max-h-48 overflow-y-auto rounded-md border bg-muted/30 p-2 font-mono text-xs leading-relaxed">
              {d.requests.map((r, i) => (
                <li key={i}>
                  <span className="text-muted-foreground">{r.method}</span> {r.path}{" "}
                  <span className="text-muted-foreground">→ {r.status}</span>
                  {r.username ? <span className="text-muted-foreground"> · user {r.username}</span> : null}
                </li>
              ))}
            </ul>
          </section>
          {v.explanation && (
            <section>
              <h3 className="text-sm font-semibold">Explanation</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{v.explanation}</p>
            </section>
          )}
        </CardContent>
      </Card>
    </aside>
  );
}

export default function Sessions({
  picked,
  onPick,
  labelFilter,
  campaignFilter,
  onFiltersChange,
}: {
  picked: string | null;
  onPick: (id: string | null) => void;
  labelFilter: Label | "all";
  campaignFilter: string | null;
  onFiltersChange: (label: Label | "all", campaignId: string | null) => void;
}) {
  const { data, error } = useQuery({ queryKey: ["sessions"], queryFn: () => api.sessions() });
  const { data: campaigns } = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns, enabled: !!campaignFilter });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!data) return <ListSkeleton rows={8} />;
  const rows = data.filter(
    (r) => (labelFilter === "all" || r.label === labelFilter) && (!campaignFilter || r.campaign_id === campaignFilter),
  );
  const selectedCampaign = campaigns?.find((campaign) => campaign.id === campaignFilter);
  const count = (l: Label | "all") =>
    data.filter((r) => (!campaignFilter || r.campaign_id === campaignFilter) && (l === "all" || r.label === l)).length;
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      <Card className="rise min-w-0 flex-1 gap-3">
        <CardHeader>
          <CardHeading
            Icon={Rows3}
            title={campaignFilter ? "Campaign sessions" : "All sessions"}
            description="Newest first · click a session to see why"
          />
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div role="group" aria-label="Filter by class" className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <Button
                key={f}
                size="sm"
                variant={labelFilter === f ? "default" : "outline"}
                aria-pressed={labelFilter === f}
                onClick={() => onFiltersChange(f, campaignFilter)}
              >
                {f === "all" ? "All" : LABEL_TEXT[f]}
                <span className="tabular-nums opacity-70">{count(f)}</span>
              </Button>
            ))}
          </div>
          {campaignFilter && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-white/[0.03] px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                Campaign filter: {selectedCampaign?.title ?? selectedCampaign?.kind ?? "Selected campaign"}
              </span>
              <Button variant="ghost" size="sm" onClick={() => onFiltersChange(labelFilter, null)}>
                Clear campaign
              </Button>
            </div>
          )}
          {rows.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No sessions match this filter.</p>
          ) : (
            <Table className="min-w-[720px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Verdict</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>IP</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead>Main reason</TableHead>
                  <TableHead>Simulator</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow
                    key={r.id}
                    data-state={picked === r.id ? "selected" : undefined}
                    className="cursor-pointer"
                    onClick={() => onPick(r.id)}
                  >
                    <TableCell className="tabular-nums text-muted-foreground">{time(r.started_at)}</TableCell>
                    <TableCell>
                      <button
                        onClick={() => onPick(r.id)}
                        aria-label={`Open session ${r.id}`}
                        className="rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                      >
                        <LabelBadge label={r.label} />
                      </button>
                    </TableCell>
                    <TableCell>
                      <ActionBadge action={r.action} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.ip}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.n_requests}</TableCell>
                    <TableCell className={cn("max-w-[340px] truncate")} title={r.reason}>
                      {r.reason}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.sim_class ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {picked && <SessionCard id={picked} onClose={() => onPick(null)} />}
    </div>
  );
}
