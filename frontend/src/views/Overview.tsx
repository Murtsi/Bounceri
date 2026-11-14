import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { ChevronRight } from "lucide-react";
import { api, type Alert } from "@/api";
import { ActionBadge } from "@/components/badges";
import { SplashScreen } from "@/components/BouncerLogo";
import { OverviewSkeleton } from "@/components/Skeletons";
import { useCountUp } from "@/lib/useCountUp";
import { pct, SegmentedBar, TrafficChart } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
            {/* Live-merkki: sykkivä lime-piste + teksti (tila ei ole pelkän värin varassa). */}
            <Badge variant="outline" className="gap-2 border-primary/40 bg-primary/10 font-semibold text-foreground">
              <span className="relative flex size-2" aria-hidden="true">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex size-2 rounded-full bg-primary" />
              </span>
              Live
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

export default function Overview({ onPick, goSessions }: { onPick: (id: string) => void; goSessions: () => void }) {
  const { data: o, error } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!o) return <OverviewSkeleton />;
  if (o.n_sessions === 0)
    return <SplashScreen message="Waiting for traffic… start the simulators: uv run python tools/sim/run.py" />;
  const h = o.honesty;
  const bad = o.distribution.bad_bot;
  return (
    <div className="flex flex-col gap-4">
      {o.alerts.map((a) => (
        <AlertCard key={a.id} a={a} onShow={goSessions} />
      ))}

      <div className="flex flex-wrap gap-4">
        <Card className="rise min-w-0 flex-[999_1_560px]" style={{ "--d": "80ms" } as CSSProperties}>
          <CardHeader>
            <CardTitle>Who came knocking</CardTitle>
            <CardDescription>Traffic over time</CardDescription>
          </CardHeader>
          <CardContent>
            <TrafficChart points={o.timeline.points} stepS={o.timeline.step_s} />
          </CardContent>
        </Card>
        <Card className="rise min-w-0 flex-[1_1_300px]" style={{ "--d": "140ms" } as CSSProperties}>
          <CardHeader>
            <CardTitle>Sessions</CardTitle>
            <CardDescription>{o.n_sessions} sessions analysed</CardDescription>
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
      </div>

      <div className="flex flex-wrap gap-4">
        <Card className="rise min-w-0 flex-[999_1_560px]" style={{ "--d": "200ms" } as CSSProperties}>
          <CardHeader>
            <CardTitle>Bad actors right now</CardTitle>
            <CardDescription>Bouncer recommends, it doesn&rsquo;t block on its own: Monitor → Rate-limit → Challenge → Block</CardDescription>
          </CardHeader>
          <CardContent>
            {o.actors.length === 0 ? (
              <p className="text-sm text-muted-foreground">No bad actors.</p>
            ) : (
              <ul className="-mx-2 flex flex-col">
                {o.actors.map((a) => (
                  <li key={a.id}>
                    <button
                      onClick={() => (a.kind === "ip" ? onPick(a.id) : goSessions())}
                      className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-2 py-3 text-left outline-none hover:bg-muted/60 focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                      <span className="flex min-w-0 flex-[999_1_280px] flex-col gap-0.5">
                        <span className="font-medium">{a.title}</span>
                        <span className="truncate text-sm text-muted-foreground">{a.detail}</span>
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
        <Card className="rise min-w-0 flex-[1_1_300px]" style={{ "--d": "260ms" } as CSSProperties}>
          <CardHeader>
            <CardTitle>How often we&rsquo;re wrong</CardTitle>
            <CardDescription>{h.synthetic ? "Simulated run — proves nothing" : "Labelled traffic"}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {h.n_humans === 0 ? (
              <p className="text-sm">No labelled humans yet.</p>
            ) : (
              <div className="rounded-lg bg-muted/60 p-4">
                <p className="text-2xl font-semibold">
                  {h.false_alarms} / {h.n_humans} humans
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  flagged as bots. The sample is small: the true rate could be as high as{" "}
                  <span className="font-medium text-foreground">
                    {Math.round((h.fpr_ci95_upper ?? 0) * 100)}%
                  </span>{" "}
                  (95% upper bound).
                </p>
              </div>
            )}
            <p className="text-sm leading-relaxed text-muted-foreground">
              Target: under 1% false alarms on humans. Claiming that needs about 300 human sessions of real
              traffic.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
