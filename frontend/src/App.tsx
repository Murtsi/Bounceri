import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, LABEL_TEXT, type Label, type SessionRow } from "./api";

type Tab = "sessions" | "campaigns" | "metrics";

const CHIP: Record<Label, string> = {
  bad_bot: "bg-red-50 text-red-800 ring-red-200",
  good_bot: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  human: "bg-blue-50 text-blue-800 ring-blue-200",
  uncertain: "bg-zinc-100 text-zinc-700 ring-zinc-300",
};

function LabelChip({ label }: { label: Label }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${CHIP[label]}`}>
      {LABEL_TEXT[label]}
    </span>
  );
}

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function SyntheticBanner({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      Synteettinen data (simulaattorit). Päätökset ovat oikeita, mutta niistä ei lasketa mittareita.
    </div>
  );
}

function Header({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  const { data: s } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const tabs: [Tab, string][] = [
    ["sessions", "Sessiot"],
    ["campaigns", "Kampanjat"],
    ["metrics", "Mittarit"],
  ];
  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-600">Bouncer</p>
          <h1 className="text-3xl font-bold">Kuka sivulla oikeasti käy</h1>
        </div>
        {s && (
          <dl className="flex flex-wrap gap-3 text-sm">
            {(Object.keys(LABEL_TEXT) as Label[]).map((l) => (
              <div key={l} className="rounded-lg bg-white px-3 py-2 ring-1 ring-zinc-200">
                <dt className="text-xs text-zinc-600">{LABEL_TEXT[l]}</dt>
                <dd className="text-xl font-semibold">{s.by_label[l] ?? 0}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      <SyntheticBanner show={!!s?.synthetic} />
      <nav aria-label="Näkymät" className="flex flex-wrap gap-2">
        {tabs.map(([t, text]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            aria-current={tab === t ? "page" : undefined}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === t ? "bg-zinc-900 text-white" : "bg-white text-zinc-800 ring-1 ring-zinc-200 hover:bg-zinc-100"
            }`}
          >
            {text}
          </button>
        ))}
        {s?.updated_at && (
          <span className="ml-auto self-center text-xs text-zinc-600">päivitetty {time(s.updated_at)}</span>
        )}
      </nav>
    </header>
  );
}

function SessionsTable({ onPick, picked }: { onPick: (id: string) => void; picked: string | null }) {
  const [filter, setFilter] = useState<Label | "all">("all");
  const { data, isLoading, error } = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  if (isLoading) return <p>Ladataan…</p>;
  if (error) return <p className="text-red-800">API ei vastaa: {String(error)}</p>;
  const rows = (data ?? []).filter((r) => filter === "all" || r.label === filter);
  return (
    <section aria-label="Sessiot" className="flex min-w-0 flex-1 flex-col gap-3">
      <label className="flex items-center gap-2 text-sm">
        Näytä
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Label | "all")}
          className="rounded-md border border-zinc-300 bg-white px-2 py-1"
        >
          <option value="all">kaikki</option>
          {(Object.keys(LABEL_TEXT) as Label[]).map((l) => (
            <option key={l} value={l}>
              {LABEL_TEXT[l]}
            </option>
          ))}
        </select>
      </label>
      {rows.length === 0 ? (
        <p className="rounded-xl bg-white p-6 text-sm text-zinc-700 ring-1 ring-zinc-200">
          Ei sessioita. Käynnistä simulaattorit: <code>uv run python tools/sim/run.py</code>
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white ring-1 ring-zinc-200">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-zinc-200 text-xs text-zinc-600">
              <tr>
                <th className="px-3 py-2">Aika</th>
                <th className="px-3 py-2">Päätös</th>
                <th className="px-3 py-2">IP</th>
                <th className="px-3 py-2">User-Agent</th>
                <th className="px-3 py-2 text-right">Pyynt.</th>
                <th className="px-3 py-2">Tärkein syy</th>
                <th className="px-3 py-2">Totuus (simulaattori)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: SessionRow) => (
                <tr
                  key={r.id}
                  className={`cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50 ${
                    picked === r.id ? "bg-blue-50" : ""
                  }`}
                  onClick={() => onPick(r.id)}
                >
                  <td className="px-3 py-2 whitespace-nowrap">{time(r.started_at)}</td>
                  <td className="px-3 py-2">
                    <button onClick={() => onPick(r.id)} className="text-left" aria-label={`Avaa sessio ${r.id}`}>
                      <LabelChip label={r.label} />
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{r.ip}</td>
                  <td className="max-w-[180px] truncate px-3 py-2 font-mono text-xs" title={r.user_agent}>
                    {r.user_agent}
                  </td>
                  <td className="px-3 py-2 text-right">{r.n_requests}</td>
                  <td className="max-w-[320px] truncate px-3 py-2" title={r.reason}>
                    {r.reason}
                  </td>
                  <td className="px-3 py-2 text-xs text-zinc-700">{r.sim_class ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SessionCard({ id, onClose }: { id: string; onClose: () => void }) {
  const { data: d } = useQuery({ queryKey: ["session", id], queryFn: () => api.session(id) });
  const ref = useRef<HTMLElement>(null);
  const loaded = !!d;
  useEffect(() => {
    // Kapealla näytöllä kortti on taulukon yläpuolella: vieritä se näkyviin.
    if (loaded && window.innerWidth < 1024) ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [id, loaded]);
  if (!d) return null;
  const v = d.verdict;
  return (
    <aside
      ref={ref}
      aria-label={`Sessio ${d.id}`}
      className="order-first flex w-full flex-col gap-3 lg:order-none lg:w-[420px] lg:shrink-0"
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-zinc-600">Sessio {d.id}</p>
        <button onClick={onClose} className="rounded-md px-2 py-1 text-sm ring-1 ring-zinc-300 hover:bg-zinc-100">
          Sulje
        </button>
      </div>
      <div className="flex flex-col gap-3 rounded-xl bg-white p-4 ring-1 ring-zinc-200">
        <div className="flex items-center justify-between">
          <LabelChip label={v.label} />
          <span className="text-xs text-zinc-600">{v.model_version}</span>
        </div>
        <div>
          <div className="flex justify-between text-xs text-zinc-600">
            <span>P(botti)</span>
            <span className="font-semibold text-zinc-900">{v.score.toFixed(2)}</span>
          </div>
          <div
            role="img"
            aria-label={`Pistemäärä ${v.score.toFixed(2)} asteikolla 0–1`}
            className="mt-1 h-2 rounded-full bg-zinc-200"
          >
            <div className="h-2 rounded-full bg-zinc-800" style={{ width: `${Math.round(v.score * 100)}%` }} />
          </div>
        </div>
        <div>
          <h2 className="text-sm font-semibold">Miksi</h2>
          <ol className="mt-1 list-decimal pl-5 text-sm leading-relaxed">
            {v.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ol>
        </div>
      </div>
      {d.campaign && (
        <div className="rounded-xl bg-white p-4 text-sm ring-1 ring-zinc-200">
          <h2 className="font-semibold">Kampanja (C)</h2>
          <p className="mt-1">
            {d.campaign.kind} · {d.campaign.size} sessiota
          </p>
          <ul className="mt-1 list-disc pl-5 text-zinc-700">
            {d.campaign.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="rounded-xl bg-white p-4 text-sm ring-1 ring-zinc-200">
        <h2 className="font-semibold">Sessio</h2>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <div>
            <dt className="text-xs text-zinc-600">IP</dt>
            <dd className="font-mono text-xs">{d.ip}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-600">DNS-varmistus (C)</dt>
            <dd>{v.verified_bot === true ? "varmistettu botti" : v.verified_bot === false ? "epäonnistui" : "—"}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs text-zinc-600">User-Agent</dt>
            <dd className="break-all font-mono text-xs">{d.user_agent}</dd>
          </div>
        </dl>
        <ul className="mt-3 max-h-48 overflow-y-auto font-mono text-xs">
          {d.requests.map((r, i) => (
            <li key={i}>
              {r.method} {r.path} → {r.status}
              {r.username ? ` (tunnus: ${r.username})` : ""}
            </li>
          ))}
        </ul>
      </div>
      {v.explanation && (
        <div className="rounded-xl bg-white p-4 text-sm ring-1 ring-zinc-200">
          <h2 className="font-semibold">Selitys (C, ilman LLM:ää)</h2>
          <p className="mt-1 leading-relaxed text-zinc-800">{v.explanation}</p>
        </div>
      )}
    </aside>
  );
}

function Campaigns() {
  const { data } = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });
  if (!data?.length) return <p className="text-sm text-zinc-700">Ei kampanjoita.</p>;
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {data.map((c) => (
        <li key={c.id} className="rounded-xl bg-white p-4 text-sm ring-1 ring-zinc-200">
          <p className="font-semibold">{c.kind}</p>
          <p className="text-xs text-zinc-600">
            {c.id} · {c.size} sessiota
          </p>
          <ul className="mt-2 list-disc pl-5">
            {c.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-2 flex flex-wrap gap-2">
            {Object.entries(c.labels ?? {}).map(([l, n]) => (
              <span key={l} className="flex items-center gap-1">
                <LabelChip label={l as Label} /> × {n}
              </span>
            ))}
          </p>
        </li>
      ))}
    </ul>
  );
}

function Metrics() {
  const { data: m } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  if (!m) return null;
  const fmt = (x: unknown) => (typeof x === "number" ? `${(x * 100).toFixed(1)} %` : "—");
  const upper = m.metrics["human_fpr_ci95_upper"];
  return (
    <section aria-label="Mittarit" className="flex flex-col gap-4">
      {(m.stub || m.synthetic_data) && (
        <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {m.stub
            ? "models/metrics.json on stub: oikeaa labeloitua liikennettä ei vielä ole. Lukuja ei näytetä eikä keksitä."
            : "Luvut on laskettu synteettisellä datalla: niillä ei ole todistusarvoa."}
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-white p-4 ring-1 ring-zinc-200">
          <p className="text-xs font-semibold text-zinc-600">Ihmisten FPR (testijakso)</p>
          <p className="text-4xl font-bold">{m.stub ? "—" : fmt(m.metrics.human_fpr)}</p>
          <p className="text-xs text-zinc-600">95 % yläraja {m.stub ? "—" : fmt(upper)} · tavoite &lt; 1 %</p>
        </div>
        <div className="rounded-xl bg-white p-4 ring-1 ring-zinc-200">
          <p className="text-xs font-semibold text-zinc-600">Epävarmojen osuus</p>
          <p className="text-4xl font-bold">{m.stub ? "—" : fmt(m.metrics["uncertain_share"])}</p>
        </div>
        <div className="rounded-xl bg-white p-4 ring-1 ring-zinc-200">
          <p className="text-xs font-semibold text-zinc-600">Malli</p>
          <p className="text-2xl font-bold">{String(m.metrics["model_version"] ?? "—")}</p>
        </div>
      </div>
      <div className="rounded-xl bg-white p-4 ring-1 ring-zinc-200">
        <h2 className="text-lg font-semibold">Mitä emme tunnista</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
          {m.known_weaknesses.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-zinc-600">
        Ingest: {JSON.stringify(m.ingest)}
      </p>
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("sessions");
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
      <Header tab={tab} setTab={setTab} />
      {tab === "sessions" && (
        <div className="flex flex-col gap-4 lg:flex-row">
          <SessionsTable onPick={setPicked} picked={picked} />
          {picked && <SessionCard id={picked} onClose={() => setPicked(null)} />}
        </div>
      )}
      {tab === "campaigns" && <Campaigns />}
      {tab === "metrics" && <Metrics />}
    </main>
  );
}
