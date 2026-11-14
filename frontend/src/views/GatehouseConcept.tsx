/* Shelved visual experiment. App.tsx does not import or render this component. */
import "./GatehouseConcept.css";
import { useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";
import { ChartColumn, ChevronRight, Pause, Play, Scale } from "lucide-react";
import { api, type Actor, type Alert } from "@/api";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { ActionBadge } from "@/components/badges";
import { SplashScreen } from "@/components/BouncerLogo";
import { OverviewSkeleton } from "@/components/Skeletons";
import { TrafficChart } from "@/components/charts";
import { Button } from "@/components/ui/button";
import { CardHeading } from "@/components/CardIcon";
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
    <button onClick={onShow} className="gate-queue-row gate-alert-row">
      <span className="gate-severity" aria-hidden="true" />
      <span className="gate-row-copy">
        <strong>{a.title}</strong>
        <span>{a.size} linked sessions · last seen {clock(a.last_seen)}</span>
        <span>{a.reasons.slice(0, 2).join(" · ")}</span>
        <span className="gate-advice">{ADVICE[a.action] ?? a.action_text}</span>
      </span>
      <span className="gate-row-action"><ActionBadge action={a.action} /><ChevronRight aria-hidden="true" /></span>
    </button>
  );
}

function TrafficGate({
  counts,
  sessionCount,
  alerts,
  actors,
  goSessions,
  showSession,
}: {
  counts: { human: number; good_bot: number; bad_bot: number; uncertain: number };
  sessionCount: number;
  alerts: Alert[];
  actors: Actor[];
  goSessions: (campaignId: string) => void;
  showSession: (sessionId: string) => void;
}) {
  const passed = counts.human + counts.good_bot;
  const [paused, setPaused] = useState(false);
  return (
    <section className={`traffic-gate${paused ? " is-paused" : ""}`} aria-label="Interactive Bouncer route illustration">
      <div className="gate-scene">
        <div className="gate-heading">
          <div className="gate-heading-copy">
            <h2>At the door</h2>
            <p>Example routes, separate from the session counts below.</p>
          </div>
          <div className="gate-scene-tools">
            <span className="gate-scene-count">{sessionCount.toLocaleString("en-GB")} sessions</span>
            <Button variant="ghost" size="sm" className="gate-replay" onClick={() => setPaused((value) => !value)} aria-label={paused ? "Resume the example traffic routes" : "Pause the example traffic routes"}>
              {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />} {paused ? "Resume" : "Pause"}
            </Button>
          </div>
        </div>
        <div className="traffic-gate-art">
          <svg viewBox="0 0 620 360" role="img" aria-label="Example routes, not session counts: a red suspicious route is stopped by the doorman, and a green approved route continues through the doorway. The dashboard does not block requests.">
          <defs>
            <linearGradient id="gate-front" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#c5ef5d" stopOpacity=".25"/><stop offset="1" stopColor="#c5ef5d" stopOpacity=".035"/></linearGradient>
            <linearGradient id="gate-side" x1="0" x2="1"><stop stopColor="#c5ef5d" stopOpacity=".18"/><stop offset="1" stopColor="#c5ef5d" stopOpacity=".025"/></linearGradient>
            <linearGradient id="gate-top" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#eef3ea" stopOpacity=".17"/><stop offset="1" stopColor="#c5ef5d" stopOpacity=".07"/></linearGradient>
            <mask id="gate-depth-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="620" height="360">
              <rect width="620" height="360" fill="white" />
              <rect x="238" y="82" width="265" height="168" fill="black" />
            </mask>
          </defs>
          <g transform="translate(0 -20)">
          <path d="M329 103 414 67 500 91 412 127Z M412 127 500 91 500 244 412 281Z" fill="url(#gate-side)" stroke="#c5ef5d" strokeOpacity=".28" strokeWidth="2" />
          <path d="M210 66 298 33 414 67 329 103Z" fill="url(#gate-top)" stroke="#eef3ea" strokeOpacity=".22" strokeWidth="2" />
          <path d="M12 263 228 266" fill="none" stroke="#ff7167" strokeOpacity=".42" strokeWidth="3" />
          <path className="traffic-flow-line" pathLength="1" d="M12 263 228 266" fill="none" stroke="#ff7167" strokeWidth="4" />
          <path d="M12 210 C88 210 158 212 218 212 L270 212 C324 212 367 210 414 205 L590 196" fill="none" stroke="#53cf8a" strokeOpacity=".55" strokeWidth="3" mask="url(#gate-depth-mask)" />
          <path className="traffic-flow-line traffic-flow-green" pathLength="1" d="M12 210 C88 210 158 212 218 212 L270 212 C324 212 367 210 414 205 L590 196" fill="none" stroke="#75e5a0" strokeWidth="4" mask="url(#gate-depth-mask)" />
          <path d="M210 66 329 103 329 277 210 240Z M235 100 297 119 297 267 235 248Z" fill="url(#gate-front)" fillRule="evenodd" stroke="#c5ef5d" strokeOpacity=".52" strokeWidth="2" />
          <path d="M298 33 414 67 500 91 382 56Z M382 56 500 91 500 244 382 210Z" fill="#c5ef5d" fillOpacity=".025" stroke="#eef3ea" strokeOpacity=".12" />
          <g className="gate-doorman" transform="translate(102 0)" aria-hidden="true">
            <path d="M126 266 153 253 176 238" fill="none" stroke="#b8c7ba" strokeWidth="12" strokeLinecap="round" />
            <path className="gate-doorman-arm" d="M179 246 197 228" fill="none" stroke="#dce7dc" strokeWidth="12" strokeLinecap="round" />
            <circle cx="164" cy="220" r="16" fill="#dce7dc" />
            <path d="M149 216Q150 198 165 201Q178 202 180 216Q169 209 149 216Z" fill="#24382b" />
            <path d="M141 241Q164 229 187 241L197 296H131Z" fill="#cbd9cc" />
            <path d="M153 239 164 254 175 239M164 254V292" fill="none" stroke="#587360" strokeWidth="2.5" />
            <path d="M181 248 163 266 145 248" fill="none" stroke="#eef4ed" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="187" cy="255" r="5" fill="#c5ef5d" />
            <path d="M164 258 159 266" fill="none" stroke="#c5ef5d" strokeWidth="2.5" />
          </g>
          <text x="17" y="250" fill="#ff8177" fontSize="10" fontWeight="700">STOPPED BY THE DOORMAN</text>
          <text x="407" y="143" fill="#9ca89a" fontSize="9">THROUGH THE DOOR</text>
          <text x="430" y="124" fill="#73d981" fontSize="10" fontWeight="700">CLEARED</text>
          <path d="M210 66v174m119-137v174m83-210v174" stroke="#eef3ea" strokeOpacity=".12" strokeDasharray="3 8" />
          </g>
          </svg>
        </div>
        <div className="gate-legend" aria-label="Actual session verdict counts">
          <span><i className="gate-dot gate-red" />Bad bot <b>{counts.bad_bot}</b></span>
          <span><i className="gate-dot gate-green" />Human / good bot <b>{passed}</b></span>
          <span><i className="gate-dot gate-gray" />Uncertain <b>{counts.uncertain}</b></span>
        </div>
      </div>
      <div className="gatehouse-queue">
        <div className="gate-queue-heading">
          <div><h2>Needs attention</h2><p>Open a session to inspect its evidence.</p></div>
          <span className="gate-queue-count">{alerts.length + actors.length}</span>
        </div>
        <div className="gate-queue-list">
          {alerts.map((a) => <AlertCard key={a.id} a={a} onShow={() => goSessions(a.id)} />)}
          {actors.slice(0, 4).map((a) => (
            <button key={a.id} onClick={() => (a.kind === "ip" ? showSession(a.id) : goSessions(a.id))} className="gate-queue-row">
              <span className="gate-severity" aria-hidden="true" />
              <span className="gate-row-copy"><strong>{a.title}</strong><span className="gate-actor-detail">{a.detail}</span><span>Last seen {clock(a.last_seen)}</span></span>
              <span className="gate-row-action"><ActionBadge action={a.action} /><ChevronRight aria-hidden="true" /></span>
            </button>
          ))}
          {alerts.length === 0 && actors.length === 0 && <p className="gate-queue-empty">No suspicious activity in the collected data.</p>}
          <Button variant="ghost" size="sm" className="gate-all-sessions" onClick={() => goSessions("")}>View all sessions <ChevronRight /></Button>
        </div>
      </div>
    </section>
  );
}

export default function GatehouseConcept({
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
  const pts = o.timeline.points;
  const activePoints = pts.filter((p) => p.human + p.good_bot + p.bad_bot + p.uncertain > 0);
  const chartPoints = activePoints.length
    ? pts.slice(pts.indexOf(activePoints[0]), pts.indexOf(activePoints[activePoints.length - 1]) + 1)
    : [];
  const requests = pts.reduce((sum, p) => sum + p.human + p.good_bot + p.bad_bot + p.uncertain, 0);
  const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;
  return (
    <div className="flex flex-col gap-5">
      <div className="overview-context">
        <span><strong>{requests.toLocaleString("en-GB")}</strong> requests</span>
        <span className="overview-context-separator" aria-hidden="true" />
        <span><strong>{o.n_sessions.toLocaleString("en-GB")}</strong> sessions</span>
        <span className="overview-context-window">Last {pts.length} × {o.timeline.step_s} s</span>
        <span className="overview-advisory">Detector classification · no live blocking</span>
      </div>

      <TrafficGate
        counts={o.distribution}
        sessionCount={o.n_sessions}
        alerts={o.alerts}
        actors={o.actors}
        goSessions={goSessions}
        showSession={showSession}
      />

      <Card className="gate-trend rise min-w-0" style={d(100)}>
        <CardHeader>
          <CardHeading Icon={ChartColumn} title="Traffic over time" description="Request volume by local verdict" />
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

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[.9fr_1.1fr]">
        <Card className="gate-humans rise min-w-0" style={d(160)}>
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
              <div className="gate-human-numbers">
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

        <div className="gate-live rise min-w-0" style={d(220)}>
          <LiveFeed onPick={onPick} />
        </div>
      </div>
    </div>
  );
}
