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

type Tab = "overview" | "sessions" | "campaigns" | "metrics";

const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["sessions", "Sessions"],
  ["campaigns", "Campaigns"],
  ["metrics", "Metrics"],
];

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

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [picked, setPicked] = useState<string | null>(null);
  const { data: s, isFetched } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  // Yleiskuva haetaan jo avausruudun aikana, jotta sen animaatiot näkyvät alusta asti.
  const { isFetched: overviewFetched } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const splash = useSplash(isFetched && overviewFetched);
  const live = splash !== "show";
  return (
    <div className="min-h-screen">
      {splash !== "gone" && <SplashOverlay leaving={splash === "leaving"} />}
      <header className="sticky top-0 z-10 border-b border-white/5 bg-[#08110c]/40 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
{/* Ponnahdus nähtiin avausruudulla; otsikossa logo on valmiina. */}
          <BouncerLogo mode="static" className="text-2xl" />
          <span className="hidden items-center gap-2 text-sm sm:inline-flex">
            <span aria-hidden="true" className="h-4 w-px bg-white/15" />
            <span className="text-muted-foreground">
              Know who&rsquo;s <em className="font-semibold not-italic text-primary">really</em> at the door
            </span>
          </span>
          <div className="ml-auto flex items-center gap-3 py-1.5">
            <span className="hidden whitespace-nowrap text-xs tabular-nums text-muted-foreground min-[400px]:inline">
              {s?.updated_at ? `updated ${time(s.updated_at)}` : ""}
            </span>
          </div>
        </div>
      </header>
      {live && (
        <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6">
          {s?.synthetic && (
            <div role="status" className="glass flex items-center gap-2 self-start rounded-full border px-4 py-2 text-sm">
              <FlaskConical className="size-4 shrink-0" style={{ color: "var(--status-warning)" }} aria-hidden="true" />
              <span>
                <span className="font-medium">Synthetic data</span>
                <span className="text-muted-foreground"> — decisions are real, but no metrics are computed from them.</span>
              </span>
            </div>
        )}
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-4">
          <TabsList aria-label="Views" className="self-start">
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
        </Tabs>
      </main>
      )}
    </div>
  );
}
