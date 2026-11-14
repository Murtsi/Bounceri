import { useQuery } from "@tanstack/react-query";
import { FileSearch, FlaskConical, Gauge, LayoutDashboard, type LucideIcon, Network, Rows3 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/api";
import { BouncerLogo, SplashOverlay } from "@/components/BouncerLogo";
import Investigations from "@/Investigations";
import { cn } from "@/lib/utils";
import Campaigns from "@/views/Campaigns";
import Metrics from "@/views/Metrics";
import Overview from "@/views/Overview";
import Sessions from "@/views/Sessions";

type Tab = "overview" | "sessions" | "campaigns" | "metrics" | "investigations";

const NAV: { id: Tab; label: string; Icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", Icon: LayoutDashboard },
  { id: "sessions", label: "Sessions", Icon: Rows3 },
  { id: "campaigns", label: "Campaigns", Icon: Network },
  { id: "metrics", label: "Metrics", Icon: Gauge },
  { id: "investigations", label: "Investigations", Icon: FileSearch },
];

const TITLE: Record<Tab, string> = {
  overview: "Overview",
  sessions: "Sessions",
  campaigns: "Campaigns",
  metrics: "Metrics",
  investigations: "Investigations",
};

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Logon ponnahdus kestää ≈ 1,55 s (index.css: viive 490 ms + 1050 ms). */
const LAUNCH_MS = 1600;

/**
 * Avausruutu poistuu vasta, kun data on tullut JA logon ponnahdus on valmis —
 * animaatio ei katkea kesken. Vähennetty liike → heti datan tultua.
 */
function useSplash(loaded: boolean): "show" | "leaving" | "gone" {
  const [state, setState] = useState<"show" | "leaving" | "gone">("show");
  const [start] = useState(() => performance.now());
  useEffect(() => {
    if (!loaded || state !== "show") return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const wait = reduced ? 0 : Math.max(0, LAUNCH_MS - (performance.now() - start));
    const t = setTimeout(() => setState("leaving"), wait);
    return () => clearTimeout(t);
  }, [loaded, state, start]);
  useEffect(() => {
    if (state !== "leaving") return;
    const t = setTimeout(() => setState("gone"), 400);
    return () => clearTimeout(t);
  }, [state]);
  return state;
}

/** Sykkivä lime-piste: data päivittyy (2 s välein). */
function LiveDot() {
  return (
    <span className="relative flex size-2" aria-hidden="true">
      <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60 motion-reduce:animate-none" />
      <span className="relative inline-flex size-2 rounded-full bg-primary" />
    </span>
  );
}

function NavButton({
  item,
  active,
  count,
  onClick,
  compact = false,
}: {
  item: (typeof NAV)[number];
  active: boolean;
  count?: number;
  onClick: () => void;
  compact?: boolean;
}) {
  const { Icon, label } = item;
  return (
    <button
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      aria-label={compact ? label : undefined}
      className={cn(
        "group flex items-center gap-3 rounded-full text-sm font-medium outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50",
        compact ? "size-12 justify-center" : "h-11 w-full px-4",
        active ? "bg-primary font-semibold text-primary-foreground" : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
      )}
    >
      <Icon className="size-[18px] shrink-0" aria-hidden="true" />
      {!compact && <span className="flex-1 text-left">{label}</span>}
      {!compact && count !== undefined && (
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs tabular-nums",
            active ? "bg-primary-foreground/15" : "bg-white/[0.06] text-muted-foreground",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [picked, setPicked] = useState<string | null>(null);
  const { data: s, isFetched } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  // Yleiskuva haetaan jo avausruudun aikana, jotta sen animaatiot näkyvät alusta asti.
  const { data: o, isFetched: overviewFetched } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const splash = useSplash(isFetched && overviewFetched);
  const live = splash !== "show";
  const counts: Partial<Record<Tab, number>> = {
    overview: o?.alerts.length,
    sessions: s?.n_sessions,
    campaigns: s?.n_campaigns,
  };
  const go = (t: Tab) => {
    setTab(t);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="min-h-screen">
      {splash !== "gone" && <SplashOverlay leaving={splash === "leaving"} />}

      {/* Sivupalkki (≥ lg): logo, navigaatio, tila alhaalla. */}
      <aside className="glass fixed inset-y-3 left-3 z-20 hidden w-60 flex-col rounded-3xl border p-4 lg:flex">
        <div className="px-2 pt-1 pb-6">
          <BouncerLogo mode="static" className="text-2xl" />
          <p className="mt-1 text-xs text-muted-foreground">
            Know who&rsquo;s <em className="font-semibold not-italic text-primary">really</em> at the door
          </p>
        </div>
        <nav aria-label="Views" className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavButton key={n.id} item={n} active={tab === n.id} count={counts[n.id]} onClick={() => go(n.id)} />
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-3 rounded-2xl border bg-white/[0.03] p-3 text-xs">
          <div className="flex items-center gap-2">
            <LiveDot />
            <span className="font-medium">Live</span>
            <span className="ml-auto tabular-nums text-muted-foreground">
              {s?.updated_at ? time(s.updated_at) : "—"}
            </span>
          </div>
          {s?.synthetic && (
            <div className="flex items-start gap-2 text-muted-foreground">
              <FlaskConical className="mt-px size-3.5 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
              <span>
                <span className="font-medium text-foreground">Synthetic data.</span> Decisions are real; no metrics
                are computed from them.
              </span>
            </div>
          )}
        </div>
      </aside>

      {/* Yläpalkki (< lg): logo + tila. */}
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-white/5 bg-[#08110c]/50 px-4 py-3 backdrop-blur-xl lg:hidden">
        <BouncerLogo mode="static" className="text-2xl" />
        <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          <LiveDot />
          {s?.updated_at ? time(s.updated_at) : "Live"}
        </span>
      </header>

      {live && (
        <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 pt-6 pb-28 lg:ml-[264px] lg:px-6 lg:pb-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{TITLE[tab]}</h1>
              {s?.synthetic && tab !== "investigations" && (
                <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground lg:hidden">
                  <FlaskConical className="size-3.5" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
                  Synthetic data — decisions are real, no metrics computed.
                </p>
              )}
            </div>
          </div>
          {tab === "overview" && (
            <Overview
              onPick={(id) => {
                setPicked(id);
                go("sessions");
              }}
              goSessions={() => go("sessions")}
            />
          )}
          {tab === "sessions" && <Sessions picked={picked} onPick={setPicked} />}
          {tab === "campaigns" && <Campaigns />}
          {tab === "metrics" && <Metrics />}
          {tab === "investigations" && (
            <div lang="en" className="investigations-view">
              <Investigations goTraffic={() => go("overview")} />
            </div>
          )}
        </main>
      )}

      {/* Kelluva navigaatio (< lg), kuten mobiilisovelluksissa. */}
      <nav
        aria-label="Views"
        className="glass fixed inset-x-0 bottom-4 z-20 mx-auto flex w-fit gap-1 rounded-full border p-1.5 lg:hidden"
      >
        {NAV.map((n) => (
          <NavButton key={n.id} item={n} active={tab === n.id} onClick={() => go(n.id)} compact />
        ))}
      </nav>
    </div>
  );
}
