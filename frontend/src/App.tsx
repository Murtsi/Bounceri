import { useQuery } from "@tanstack/react-query";
import { FileSearch, FlaskConical, Gauge, LayoutDashboard, type LucideIcon, Network, Rows3 } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "@/api";
import { BouncerLogo, SplashOverlay } from "@/components/BouncerLogo";
import { SYNTHETIC_DATA_NOTICE } from "@/content";
import { activityStatus } from "@/lib/activity";
import { cn } from "@/lib/utils";

const Investigations = lazy(() => import("@/Investigations"));
const Landing = lazy(() => import("@/views/Landing"));
const Campaigns = lazy(() => import("@/views/Campaigns"));
const Metrics = lazy(() => import("@/views/Metrics"));
const Overview = lazy(() => import("@/views/Overview"));
const Sessions = lazy(() => import("@/views/Sessions"));

/** "home" = etusivu (landing, ei sivupalkkia); muut ovat dashboardin näkymiä. */
type Tab = "home" | "overview" | "sessions" | "campaigns" | "metrics" | "investigations";
type SessionLabel = "bad_bot" | "good_bot" | "human" | "uncertain";
type RouteState = { tab: Tab; campaignId: string | null; label: SessionLabel | "all"; sessionId: string | null };

const TABS = new Set<Tab>(["home", "overview", "sessions", "campaigns", "metrics", "investigations"]);
const LABELS = new Set<SessionLabel>(["bad_bot", "good_bot", "human", "uncertain"]);

function readRoute(): RouteState {
  const params = new URLSearchParams(window.location.search);
  const rawTab = params.get("tab") as Tab | null;
  const rawLabel = params.get("label") as SessionLabel | null;
  return {
    // Ilman tab-parametria avautuu etusivu; dashboard on ?tab=overview (päätös 066).
    tab: rawTab && TABS.has(rawTab) ? rawTab : "home",
    campaignId: params.get("campaign"),
    label: rawLabel && LABELS.has(rawLabel) ? rawLabel : "all",
    sessionId: params.get("session"),
  };
}

function routeUrl(route: RouteState) {
  const params = new URLSearchParams();
  if (route.tab !== "home") params.set("tab", route.tab);
  if (route.campaignId) params.set("campaign", route.campaignId);
  if (route.label !== "all") params.set("label", route.label);
  if (route.sessionId) params.set("session", route.sessionId);
  const query = params.toString();
  return `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
}

const NAV: { id: Exclude<Tab, "home">; label: string; Icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", Icon: LayoutDashboard },
  { id: "sessions", label: "Sessions", Icon: Rows3 },
  { id: "campaigns", label: "Campaigns", Icon: Network },
  { id: "metrics", label: "Metrics", Icon: Gauge },
  { id: "investigations", label: "Investigations", Icon: FileSearch },
];

const TITLE: Record<Tab, string> = {
  home: "Bounceri",
  overview: "Overview",
  sessions: "Sessions",
  campaigns: "Campaigns",
  metrics: "Metrics",
  investigations: "Investigations",
};

/** Logon ponnahdus kestää ≈ 1,55 s (index.css: viive 490 ms + 1050 ms). */
const LAUNCH_MS = 900;

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
        "group flex items-center gap-3 text-sm font-medium outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50",
        compact ? "size-12 justify-center rounded-full" : "h-10 w-full rounded-lg px-3",
        compact
          ? active
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
          : active
            ? "bg-white/[0.07] text-foreground [&_svg]:text-primary"
            : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground",
      )}
    >
      <Icon className="size-[18px] shrink-0" aria-hidden="true" />
      {!compact && <span className="flex-1 text-left">{label}</span>}
      {!compact && count !== undefined && (
        <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
      )}
    </button>
  );
}

export default function App() {
  const [route, setRoute] = useState<RouteState>(readRoute);
  const { data: s, isFetched } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  // Yleiskuva haetaan jo avausruudun aikana, jotta sen animaatiot näkyvät alusta asti.
  const { data: o, isFetched: overviewFetched } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const splash = useSplash(isFetched && overviewFetched);
  const live = splash !== "show";
  const activity = activityStatus(o?.now);
  const tab = route.tab;
  const counts: Partial<Record<Tab, number>> = {
    overview: o?.alerts.length,
    sessions: s?.n_sessions,
    campaigns: s?.n_campaigns,
  };
  useEffect(() => {
    const restore = () => setRoute(readRoute());
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);

  const navigate = (next: RouteState) => {
    setRoute(next);
    window.history.pushState(null, "", routeUrl(next));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const go = (t: Tab) => navigate({ tab: t, campaignId: null, label: "all", sessionId: null });
  const showCampaign = (campaignId: string) =>
    navigate({ tab: "sessions", campaignId, label: "all", sessionId: null });
  const showSession = (sessionId: string) => navigate({ ...route, tab: "sessions", sessionId });

  if (tab === "home")
    return (
      <>
        {splash !== "gone" && <SplashOverlay leaving={splash === "leaving"} />}
        {live && (
          <Suspense fallback={null}>
            <Landing open={(t) => go(t)} />
          </Suspense>
        )}
      </>
    );

  return (
    <div className="min-h-screen">
      {splash !== "gone" && <SplashOverlay leaving={splash === "leaving"} />}

      {/* Sivupalkki (≥ lg): logo, navigaatio, tila alhaalla. */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[232px] flex-col border-r border-white/[0.07] bg-[#07100b]/80 px-4 py-6 lg:flex">
        <div className="px-3 pb-8">
          <button type="button" onClick={() => go("home")} aria-label="Bounceri home" className="rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
            <BouncerLogo mode="static" className="text-2xl" />
          </button>
          <p className="mt-1 text-xs text-muted-foreground">
            Know who&rsquo;s <em className="font-semibold not-italic text-primary">really</em> at the door
          </p>
        </div>
        <nav aria-label="Views" className="flex flex-col gap-0.5">
          {NAV.map((n) => (
            <NavButton key={n.id} item={n} active={tab === n.id} count={counts[n.id]} onClick={() => go(n.id)} />
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-3 border-t border-white/[0.07] px-3 pt-4 text-xs">
          <div className="flex items-center gap-2">
            {activity.live && <LiveDot />}
            <span className="font-medium">{activity.label}</span>
            <span className="ml-auto tabular-nums text-muted-foreground">{activity.time ?? "—"}</span>
          </div>
          {s?.synthetic && (
            <div className="flex items-center gap-2 text-muted-foreground" title={SYNTHETIC_DATA_NOTICE}>
              <FlaskConical className="size-3.5 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
              <span>Synthetic traffic</span>
            </div>
          )}
        </div>
      </aside>

      {/* Yläpalkki (< lg): logo + tila. */}
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-white/5 bg-[#08110c]/50 px-4 py-3 backdrop-blur-xl lg:hidden">
        <BouncerLogo mode="static" className="text-2xl" />
        <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          {activity.live && <LiveDot />}
          <span>{activity.label}{activity.time ? ` · ${activity.time}` : ""}</span>
        </span>
      </header>

      {live && (
        <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 pt-6 pb-28 lg:ml-[232px] lg:px-10 lg:pt-9 lg:pb-16">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{TITLE[tab]}</h1>
              {s?.synthetic && tab !== "investigations" && (
                <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground lg:hidden">
                  <FlaskConical className="size-3.5" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
                  {SYNTHETIC_DATA_NOTICE}
                </p>
              )}
            </div>
          </div>
          <Suspense fallback={<div role="status" className="min-h-40 text-sm text-muted-foreground">Loading view…</div>}>
          {tab === "overview" && (
            <Overview
              onPick={(id) => {
                showSession(id);
              }}
              goSessions={showCampaign}
              showSession={showSession}
            />
          )}
          {tab === "sessions" && (
            <Sessions
              picked={route.sessionId}
              onPick={(sessionId) => navigate({ ...route, tab: "sessions", sessionId })}
              labelFilter={route.label}
              campaignFilter={route.campaignId}
              onFiltersChange={(label, campaignId) =>
                navigate({ ...route, tab: "sessions", label, campaignId, sessionId: null })
              }
            />
          )}
          {tab === "campaigns" && <Campaigns onShowSessions={showCampaign} />}
          {tab === "metrics" && <Metrics />}
          {tab === "investigations" && (
            <div lang="en" className="investigations-view">
              <Investigations goTraffic={() => go("overview")} />
            </div>
          )}
          </Suspense>
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
