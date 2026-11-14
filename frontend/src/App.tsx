import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/api";
import { BouncerLogo, SplashOverlay } from "@/components/BouncerLogo";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Overview from "@/views/Overview";
import Campaigns from "@/views/Campaigns";
import Metrics from "@/views/Metrics";
import Sessions from "@/views/Sessions";
import Investigations from "@/Investigations";

type Tab = "overview" | "sessions" | "campaigns" | "metrics" | "investigations";

const TABS: [Tab, string][] = [
  ["overview", "Yleiskuva"],
  ["sessions", "Sessiot"],
  ["campaigns", "Kampanjat"],
  ["metrics", "Mittarit"],
  ["investigations", "Investigations"],
];

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Avausruutu näkyy vähintään yhden logo-pompun ajan, sitten häivytys (380 ms). */
function useSplash(loaded: boolean): "show" | "leaving" | "gone" {
  const [minDone, setMinDone] = useState(false);
  const [state, setState] = useState<"show" | "leaving" | "gone">("show");
  useEffect(() => {
    const t = setTimeout(() => setMinDone(true), 1100);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (loaded && minDone && state === "show") setState("leaving");
  }, [loaded, minDone, state]);
  useEffect(() => {
    if (state !== "leaving") return;
    const t = setTimeout(() => setState("gone"), 400);
    return () => clearTimeout(t);
  }, [state]);
  return state;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [picked, setPicked] = useState<string | null>(null);
  const { data: s, isFetched } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const splash = useSplash(isFetched);
  return (
    <div className="min-h-screen">
      {splash !== "gone" && <SplashOverlay leaving={splash === "leaving"} />}
      <header className="sticky top-0 z-10 border-b border-white/5 bg-[#08110c]/40 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <BouncerLogo mode="play" className="text-2xl" />
          <span className="hidden text-sm text-muted-foreground sm:inline">Kuka sivulla oikeasti käy</span>
          <div className="ml-auto flex items-center gap-3 py-1.5">
            <span className="hidden whitespace-nowrap text-xs tabular-nums text-muted-foreground min-[400px]:inline">
              {s?.updated_at ? `päivitetty ${time(s.updated_at)}` : ""}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6">
        {s?.synthetic && tab !== "investigations" && (
          <div role="status" className="glass flex items-center gap-2 self-start rounded-full border px-4 py-2 text-sm">
            <FlaskConical className="size-4 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
            <span>
              <span className="font-medium">Synteettinen data</span>
              <span className="text-muted-foreground"> — päätökset ovat oikeita, mutta niistä ei lasketa mittareita.</span>
            </span>
          </div>
        )}
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-4">
          <TabsList aria-label="Näkymät" className="self-start">
            {TABS.map(([t, text]) => (
              <TabsTrigger key={t} value={t}>
                {text}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="overview">
            <Overview
              onPick={(id) => {
                setPicked(id);
                setTab("sessions");
              }}
              goSessions={() => setTab("sessions")}
            />
          </TabsContent>
          <TabsContent value="sessions">
            <Sessions picked={picked} onPick={setPicked} />
          </TabsContent>
          <TabsContent value="campaigns">
            <Campaigns />
          </TabsContent>
          <TabsContent value="metrics">
            <Metrics />
          </TabsContent>
          <TabsContent value="investigations" lang="en" className="investigations-view">
            <Investigations goTraffic={() => setTab("overview")} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
