import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { Activity, Bot, ChartColumn, ChevronRight, Crosshair, PieChart, Scale, ShieldAlert, Users } from "lucide-react";
import { api, type Alert } from "@/api";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { ActionBadge } from "@/components/badges";
import { SplashScreen } from "@/components/BouncerLogo";
import { OverviewSkeleton } from "@/components/Skeletons";
import { useCountUp } from "@/lib/useCountUp";
import { pct, SegmentedBar, TrafficChart } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardHeading } from "@/components/CardIcon";
import { Kpi } from "@/components/Kpi";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LiveFeed } from "@/views/LiveFeed";

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const ADVICE: Record<string, string> = {
  rate_limit:
    "Rate-limit login attempts per account and require extra verification. Blocking IPs won't help: the attacker keeps switching addresses.",
};

function AlertCard({ a, onShow }: { a: Alert; onShow: () => void }) {
  return (
    <Card className="rise gap-0 overflow-hidden py-0">
      <div className="flex flex-wrap">
        <div className="flex min-w-0 flex-[999_1_460px] flex-col gap-3 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-2 border-primary/40 bg-primary/10 font-semibold text-foreground">
              Observed in this run
            </Badge>
            <span className="text-sm tabular-nums text-muted-foreground">
              started {clock(a.started_at)} · last seen {clock(a.last_seen)} · {Math.round(a.duration_s)} s
            </span>
          </div>
          <h2 className="break-words text-2xl font-semibold leading-tight tracking-tight [hyphens:auto] sm:text-3xl">
            {a.title}
          </h2>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Every attempt came from a different address, so no single IP looks suspicious. Bouncer linked them to
            one actor because the account, tool and timing all match.
          </p>
          <ul className="flex flex-wrap gap-2">
            {a.reasons.map((r) => (
              <li key={r}>
                <Badge variant="secondary" className="font-normal">
                  {r}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex min-w-0 flex-[1_1_280px] flex-col justify-between gap-4 border-t bg-muted/50 p-6 sm:border-t-0 sm:border-l">
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Recommended</p>
            <div>
              <ActionBadge action={a.action} />
            </div>
            <p className="text-sm leading-relaxed">{ADVICE[a.action] ?? a.action_text}</p>
          </div>
          <Button onClick={onShow} className="w-fit">
            Show {a.size} sessions <ChevronRight />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function HeroPct({ value }: { value: number }) {
  const v = useCountUp(value);
  return <p className="text-5xl font-semibold tabular-nums tracking-tight">{v}%</p>;
}

export default function Overview({
  onPick,
  goSessions,
  showSession,
}: {
  onPick: (id: string) => void;
  goSessions: (campaignId: string) => void;
  showSession: (sessionId: string) => void;
}) {
  const { data: o, error } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!o) return <OverviewSkeleton />;
  if (o.n_sessions === 0)
    return <SplashScreen message="Waiting for traffic… start the simulators: uv run python tools/sim/run.py" />;
  const h = o.honesty;
  const bad = o.distribution.bad_bot;
  const pts = o.timeline.points;
  const activePoints = pts.filter((p) => p.human + p.good_bot + p.bad_bot + p.uncertain > 0);
  const chartPoints = activePoints.length
    ? pts.slice(pts.indexOf(activePoints[0]), pts.indexOf(activePoints[activePoints.length - 1]) + 1)
    : [];
  const totals = pts.map((p) => p.human + p.good_bot + p.bad_bot + p.uncertain);
  const requests = totals.reduce((x, y) => x + y, 0);
  const badReq = pts.map((p) => p.bad_bot);
  const blocked = o.actors.filter((x) => x.action === "block").length;
  const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;
  return (
    <div className="flex flex-col gap-4">
      {/* Tunnusluvut: neljä vastausta yhdellä silmäyksellä. */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <Kpi Icon={Activity} label="Requests" value={requests} note={`last ${pts.length} × ${o.timeline.step_s} s`} spark={totals} color="var(--ink-muted)" />
        <Kpi Icon={Users} label="Sessions" value={o.n_sessions} note={`${o.distribution.human} classified Human · ${o.distribution.good_bot} good bot`} delay={60} />
        <Kpi Icon={Bot} label="Bad bots" value={bad} note={`${pct(bad, o.n_sessions)}% of sessions`} spark={badReq} color="var(--series-bad)" delay={120} />
        <Kpi Icon={ShieldAlert} label="Login attacks" value={o.alerts.length} note={`${blocked} block recommendations · last 10 min of collected traffic`} delay={180} accent={o.alerts.length > 0} />
      </div>

      {o.alerts.map((a) => (
        <AlertCard key={a.id} a={a} onShow={() => goSessions(a.id)} />
      ))}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="rise min-w-0 lg:col-span-2" style={d(80)}>
          <CardHeader>
            <CardHeading Icon={ChartColumn} title="Who came knocking" description="Traffic over time, by verdict" />
          </CardHeader>
          <CardContent>
            {chartPoints.length > 0 ? (
              <TrafficChart
                points={chartPoints}
                stepS={o.timeline.step_s}
                emptyIntervalsHidden={chartPoints.length < pts.length}
              />
            ) : (
              <p className="text-sm text-muted-foreground">No requests in the available time window.</p>
            )}
          </CardContent>
        </Card>

        <Card className="rise min-w-0" style={d(140)}>
          <CardHeader>
            <CardHeading Icon={PieChart} title="Traffic mix" description={`${o.n_sessions} sessions analysed`} />
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {/* Näkymän ainoa hero-luku (dataviz: yksi per näkymä). */}
            <div>
              <HeroPct value={pct(bad, o.n_sessions)} />
              <p className="text-sm text-muted-foreground">of sessions are bad bots ({bad})</p>
            </div>
            <SegmentedBar counts={o.distribution} total={o.n_sessions} />
            <p className="text-xs leading-relaxed text-muted-foreground">
              “Uncertain” = Bouncer isn&rsquo;t sure enough, so it doesn&rsquo;t guess.
            </p>
          </CardContent>
        </Card>

        <Card className="rise min-w-0 lg:col-span-2" style={d(200)}>
          <CardHeader>
            <CardHeading
              Icon={Crosshair}
              title="Bad actors observed"
              description="Latest known activity · recommendations do not block traffic"
            />
          </CardHeader>
          <CardContent>
            {o.actors.length === 0 ? (
              <p className="text-sm text-muted-foreground">No bad actors in the collected data.</p>
            ) : (
              <ul className="-mx-2 flex flex-col">
                {o.actors.map((a) => (
                  <li key={a.id}>
                    <button
                      onClick={() => (a.kind === "ip" ? showSession(a.id) : goSessions(a.id))}
                      className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl px-2 py-3 text-left outline-none hover:bg-white/[0.05] focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                      <span className="flex min-w-0 flex-[999_1_280px] flex-col gap-0.5">
                        <span className="font-medium">{a.title}</span>
                        <span className="truncate text-sm text-muted-foreground">{a.detail}</span>
                        <span className="text-xs text-muted-foreground">Last seen {clock(a.last_seen)}</span>
                      </span>
                      <ActionBadge action={a.action} />
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="rise min-w-0" style={d(260)}>
          <CardHeader>
            <CardHeading
              Icon={Scale}
              title="Known human sessions"
              description={h.synthetic ? SYNTHETIC_DATA_NOTICE : "Labelled traffic · outcomes are not identity verification"}
            />
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {h.n_humans === 0 ? (
              <p className="text-sm">No labelled humans yet.</p>
            ) : h.n_scored === 0 ? (
              <p className="text-sm">Known human sessions have not received a verdict yet.</p>
            ) : (
              <div className="rounded-2xl bg-white/[0.04] p-4">
                <dl className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm text-muted-foreground">Flagged as bots</dt>
                    <dd className="text-2xl font-semibold">{h.false_alarms} / {h.n_scored}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted-foreground">Left uncertain</dt>
                    <dd className="text-2xl font-semibold">{h.verdicts.uncertain} / {h.n_scored}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {h.n_humans - h.n_scored > 0 && `${h.n_humans - h.n_scored} known human sessions have no verdict. `}
                  {h.false_alarms} of {h.n_scored} scored human sessions were flagged. The estimated false-alarm rate could be as high as{" "}
                  <span className="font-medium text-foreground">{Math.round((h.fpr_ci95_upper ?? 0) * 100)}%</span>{" "}
                  (95% upper bound).
                </p>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  {h.model_versions.length === 1 && h.model_versions[0] === "rules-v1"
                    ? "The rules-v1 detector never labels a session Human; uncertain means it did not have enough evidence for a confident verdict."
                    : "Uncertain is not a Human verdict; it means the detector did not have enough evidence for a confident call."}
                </p>
              </div>
            )}
            <p className="text-sm leading-relaxed text-muted-foreground">
              Target: under 1% false alarms on humans. Establishing that needs about 300 labelled human sessions.
            </p>
          </CardContent>
        </Card>

        <div className="rise min-w-0 lg:col-span-3" style={d(320)}>
          <LiveFeed onPick={onPick} />
        </div>
      </div>
    </div>
  );
}
