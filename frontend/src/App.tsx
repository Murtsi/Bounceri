import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { api } from "@/api";
import { BouncerLogo } from "@/components/BouncerLogo";
import { ThemeToggle } from "@/components/ThemeToggle";
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

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [picked, setPicked] = useState<string | null>(null);
  const { data: s } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <BouncerLogo mode="play" className="text-2xl" />
          <span className="hidden text-sm text-muted-foreground sm:inline">Kuka sivulla oikeasti käy</span>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden whitespace-nowrap text-xs tabular-nums text-muted-foreground min-[400px]:inline">
              {s?.updated_at ? `päivitetty ${time(s.updated_at)}` : ""}
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6">
        {s?.synthetic && tab !== "investigations" && (
          <div role="status" className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm">
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
