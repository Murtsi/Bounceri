import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { api } from "@/api";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { ActionBadge } from "@/components/badges";
import { SplashScreen } from "@/components/BouncerLogo";
import { OverviewSkeleton } from "@/components/Skeletons";
import { TrafficChart } from "@/components/charts";
import { Button } from "@/components/ui/button";
import { GatehouseScene, type GateMode } from "@/views/GatehouseScene";
import { LiveFeed } from "@/views/LiveFeed";

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const ADVICE: Record<string, string> = {
  rate_limit: "Rate-limit login attempts per account and require extra verification. Blocking IPs won't help: the attacker keeps switching addresses.",
};

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
  const [gateMode, setGateMode] = useState<GateMode>("idle");
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!o) return <OverviewSkeleton />;
  if (o.n_sessions === 0)
    return <SplashScreen message="Waiting for traffic… start the simulators: uv run python tools/sim/run.py" />;
  const h = o.honesty;
  const pts = o.timeline.points;
  const activePoints = pts.filter((p) => p.human + p.good_bot + p.bad_bot + p.uncertain > 0);
  const chartPoints = activePoints.length
    ? pts.slice(pts.indexOf(activePoints[0]), pts.indexOf(activePoints[activePoints.length - 1]) + 1)
    : [];
  const requests = pts.reduce((sum, p) => sum + p.human + p.good_bot + p.bad_bot + p.uncertain, 0);
  return (
    <div className="overview-stack">
      <div className="overview-context">
        <span><strong>{requests.toLocaleString("en-GB")}</strong> requests</span>
        <span className="overview-context-separator" aria-hidden="true" />
        <span><strong>{o.n_sessions.toLocaleString("en-GB")}</strong> sessions</span>
        <span className="overview-context-window">Last {pts.length} × {o.timeline.step_s} s</span>
        <span className="overview-advisory">Detector classification · no live blocking</span>
      </div>

      {/* Näyteikkuna: jokainen piste on oikea sessio Bouncerin luokittelemana. */}
      <section className="showcase" aria-labelledby="showcase-title">
        <div className="showcase-copy">
          <h2 id="showcase-title">
            Every session meets <span>the bouncer.</span>
          </h2>
          <p className="showcase-lede">
            Each dot is a real session, sorted by Bouncer as it arrives.
          </p>
          <ul className="showcase-legend">
            <li><i className="sw sw-pass" aria-hidden="true" />Walks through · human or good bot</li>
            <li><i className="sw sw-stop" aria-hidden="true" />Held at the door · bad bot</li>
            <li><i className="sw sw-check" aria-hidden="true" />Checked, then let in · uncertain</li>
          </ul>
          <p className={`showcase-mode is-${gateMode}`} role="status">
            <i aria-hidden="true" />
            {gateMode === "live"
              ? "Live · following incoming sessions"
              : gateMode === "replay"
                ? "No new traffic · replaying the latest sessions"
                : "Waiting for traffic"}
          </p>
          <p className="showcase-note">Illustration. Bouncer recommends actions; it never blocks requests itself.</p>
        </div>
        <div className="showcase-scene">
          <GatehouseScene onMode={setGateMode} />
        </div>
      </section>
      <section className="attention-panel" aria-labelledby="attention-title">
        <div className="attention-heading">
          <div>
            <h2 id="attention-title">Needs attention</h2>
            <p>Open a finding to inspect its evidence.</p>
          </div>
          <span className="attention-count">{o.alerts.length + o.actors.length}</span>
        </div>
        <div className="attention-list">
          {o.alerts.map((a) => (
            <button key={a.id} onClick={() => goSessions(a.id)} className="attention-row">
              <span className="attention-severity" aria-hidden="true" />
              <span className="attention-copy">
                <strong>{a.title}</strong>
                <span>{a.size} linked sessions · last seen {clock(a.last_seen)}</span>
                <span>{a.reasons.slice(0, 2).join(" · ")}</span>
                <span className="attention-advice">{ADVICE[a.action] ?? a.action_text}</span>
              </span>
              <span className="attention-action"><ActionBadge action={a.action} /><ChevronRight aria-hidden="true" /></span>
            </button>
          ))}
          {o.actors.slice(0, 4).map((a) => (
            <button key={a.id} onClick={() => (a.kind === "ip" ? showSession(a.id) : goSessions(a.id))} className="attention-row">
              <span className="attention-severity" aria-hidden="true" />
              <span className="attention-copy">
                <strong>{a.title}</strong><span>{a.detail}</span><span>Last seen {clock(a.last_seen)}</span>
              </span>
              <span className="attention-action"><ActionBadge action={a.action} /><ChevronRight aria-hidden="true" /></span>
            </button>
          ))}
          {o.alerts.length === 0 && o.actors.length === 0 && <p className="attention-empty">No suspicious activity in the collected data.</p>}
          <Button variant="ghost" size="sm" className="attention-all" onClick={() => goSessions("")}>View all sessions <ChevronRight /></Button>
        </div>
      </section>

      {/* Todisteet: liikenne aikajanalla ja uusimmat sessiot rinnakkain, ilman kortteja. */}
      <div className="overview-evidence">
        <section className="overview-section min-w-0" aria-labelledby="traffic-title">
          <header className="section-head">
            <h2 id="traffic-title">Traffic over time</h2>
            <p>Request volume by local verdict</p>
          </header>
          {chartPoints.length > 0 ? (
            <TrafficChart
              points={chartPoints}
              stepS={o.timeline.step_s}
              emptyIntervalsHidden={chartPoints.length < pts.length}
              hideTotal
            />
          ) : (
            <p className="text-sm text-muted-foreground">No requests in the available time window.</p>
          )}
        </section>
        <div className="overview-section min-w-0">
          <LiveFeed onPick={onPick} limit={6} />
        </div>
      </div>

      {/* Rehellisyys: tunnetut ihmiset alaviitteenä, ei omana korttina. */}
      <section className="overview-honesty" aria-labelledby="humans-title">
        <header className="section-head">
          <h2 id="humans-title">Known human sessions</h2>
          <p>{h.synthetic ? SYNTHETIC_DATA_NOTICE : "Labelled traffic · outcomes are not identity verification"}</p>
        </header>
        <div className="flex flex-col gap-3">
            {h.n_humans === 0 ? (
              <p className="text-sm">No labelled humans yet.</p>
            ) : h.n_scored === 0 ? (
              <p className="text-sm">Known human sessions have not received a verdict yet.</p>
            ) : (
              <div className="human-numbers">
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
          </div>
      </section>
    </div>
  );
}
