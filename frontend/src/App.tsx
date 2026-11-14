import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { api } from "@/api";
import { BouncerLogo } from "@/components/BouncerLogo";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Overview from "@/views/Overview";
import Campaigns from "@/views/Campaigns";
import Metrics from "@/views/Metrics";
import Sessions from "@/views/Sessions";

type Tab = "overview" | "sessions" | "campaigns" | "metrics";

const TABS: [Tab, string][] = [
  ["overview", "Yleiskuva"],
  ["sessions", "Sessiot"],
  ["campaigns", "Kampanjat"],
  ["metrics", "Mittarit"],
];

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [picked, setPicked] = useState<string | null>(null);
  const { data: s } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  return (
    <div className="min-h-screen">
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
        {s?.synthetic && (
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
        </Tabs>
      </main>
    </div>
  );
}
