import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, LABEL_TEXT, type Action, type Alert, type Label } from "./api";

// Värit eroavat myös vaaleudeltaan (ei pelkkä sävy).
export const LABEL_COLOR: Record<Label, string> = {
  human: "#2F6FE0",
  good_bot: "#2E8B57",
  uncertain: "#9AA0AA",
  bad_bot: "#C0352B",
};
const ORDER: Label[] = ["human", "good_bot", "uncertain", "bad_bot"];

const ACTION_STYLE: Record<Action, string> = {
  block: "bg-zinc-900 text-white",
  challenge: "bg-orange-100 text-orange-900",
  rate_limit: "bg-red-100 text-red-900",
  monitor: "bg-zinc-100 text-zinc-800",
  none: "bg-zinc-100 text-zinc-800",
};

const ACTION_ADVICE: Partial<Record<Action, string>> = {
  rate_limit:
    "Rajoita kirjautumisyrityksiä per tunnus ja vaadi lisätunnistus. IP-esto ei auta: hyökkääjä vaihtaa osoitetta.",
  block: "Estä IP-osoite reunalla (esim. Caddy). Liikenne on yksiselitteisesti haitallista.",
  challenge: "Näytä haaste (CAPTCHA tai JS-tarkistus) ennen estoa: todennäköinen, ei varma botti.",
};

function clock(iso: string, seconds = false) {
  return new Date(iso).toLocaleTimeString("fi-FI", {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
  });
}

function pct(n: number, total: number) {
  return total ? Math.round((n / total) * 100) : 0;
}

export function ActionChip({ action, text }: { action: Action; text: string }) {
  return <span className={`rounded-lg px-2.5 py-1 text-sm font-semibold ${ACTION_STYLE[action]}`}>{text}</span>;
}

function AlertCard({ a, onShow }: { a: Alert; onShow: () => void }) {
  return (
    <section
      aria-label="Käynnissä oleva hyökkäys"
      className="flex flex-wrap gap-5 overflow-hidden rounded-2xl border border-red-200 bg-white p-5"
    >
      <div className="flex min-w-0 flex-[999_1_480px] flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-red-700 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide text-white">
            Käynnissä
          </span>
          <span className="text-sm text-zinc-600">
            alkoi {clock(a.started_at, true)} · viimeksi {clock(a.last_seen, true)} · kesto{" "}
            {Math.round(a.duration_s)} s
          </span>
        </div>
        <h2 className="break-words text-2xl font-bold leading-tight [hyphens:auto]">{a.title}</h2>
        <p className="max-w-2xl text-sm leading-relaxed text-zinc-700">
          Jokainen yritys tuli eri osoitteesta, joten yksittäinen IP ei näytä epäilyttävältä. Bouncer yhdisti ne
          samaksi toimijaksi:
        </p>
        <ul className="flex flex-wrap gap-2 text-sm">
          {a.reasons.map((r) => (
            <li key={r} className="rounded-md bg-zinc-100 px-2 py-1 text-zinc-800">
              {r}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-2 rounded-xl bg-red-50 p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-red-900">Suositus</p>
        <p className="text-xl font-bold">{a.action_text} kirjautumista</p>
        <p className="text-sm leading-relaxed text-zinc-800">{ACTION_ADVICE[a.action]}</p>
        <div>
          <button
            onClick={onShow}
            className="rounded-lg bg-zinc-900 px-3.5 py-2.5 text-sm font-semibold text-white hover:bg-zinc-700"
          >
            Näytä {a.size} sessiota
          </button>
        </div>
      </div>
    </section>
  );
}

function Timeline({ data, step }: { data: ({ t: string } & Record<Label, number>)[]; step: number }) {
  const rows = data.map((p) => ({ ...p, label: clock(p.t, step < 60) }));
  return (
    <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-3 rounded-2xl bg-white p-5 ring-1 ring-zinc-200">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Kuka sivulla kävi</h2>
        <span className="text-xs text-zinc-600">pyyntöä / {step < 60 ? `${step} s` : `${step / 60} min`}</span>
      </div>
      <div className="h-56" role="img" aria-label="Pinottu pylväskaavio pyynnöistä aikaväleittäin luokan mukaan">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="#EEEFF1" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={24} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            {ORDER.map((l) => (
              <Bar key={l} dataKey={l} name={LABEL_TEXT[l]} stackId="a" fill={LABEL_COLOR[l]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-700">
        {ORDER.map((l) => (
          <li key={l} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-3 w-3 rounded-sm" style={{ background: LABEL_COLOR[l] }} />
            {LABEL_TEXT[l]}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Distribution({ dist, total }: { dist: Record<Label, number>; total: number }) {
  return (
    <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-3 rounded-2xl bg-white p-5 ring-1 ring-zinc-200">
      <h2 className="text-lg font-semibold">Sessiot</h2>
      <div
        role="img"
        aria-label={ORDER.map((l) => `${LABEL_TEXT[l]} ${pct(dist[l], total)} %`).join(", ")}
        className="flex h-3.5 overflow-hidden rounded-full bg-zinc-100"
      >
        {ORDER.map((l) => (
          <span key={l} style={{ width: `${pct(dist[l], total)}%`, background: LABEL_COLOR[l] }} />
        ))}
      </div>
      <dl className="grid grid-cols-2 gap-3">
        {ORDER.map((l) => (
          <div key={l}>
            <dt className="text-xs text-zinc-600">{LABEL_TEXT[l]}</dt>
            <dd className="text-2xl font-bold">
              {dist[l]} <span className="text-sm font-medium text-zinc-600">({pct(dist[l], total)} %)</span>
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-xs leading-relaxed text-zinc-600">
        {total} sessiota. ”Epävarma” = Bouncer ei ole tarpeeksi varma, joten se ei arvaa.
      </p>
    </div>
  );
}

export default function Overview({ onPick, goSessions }: { onPick: (id: string) => void; goSessions: () => void }) {
  const { data: o, error } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  if (error) return <p className="text-red-800">API ei vastaa: {String(error)}</p>;
  if (!o) return <p>Ladataan…</p>;
  if (o.n_sessions === 0)
    return (
      <p className="rounded-xl bg-white p-6 text-sm ring-1 ring-zinc-200">
        Ei vielä liikennettä. Käynnistä simulaattorit: <code>uv run python tools/sim/run.py</code>
      </p>
    );
  const h = o.honesty;
  return (
    <div className="flex flex-col gap-5">
      {o.alerts.map((a) => (
        <AlertCard key={a.id} a={a} onShow={goSessions} />
      ))}
      <div className="flex flex-wrap gap-4">
        <Timeline data={o.timeline.points} step={o.timeline.step_s} />
        <Distribution dist={o.distribution} total={o.n_sessions} />
      </div>
      <div className="flex flex-wrap gap-4">
        <section
          aria-label="Haitalliset toimijat"
          className="flex min-w-0 flex-[999_1_560px] flex-col gap-2 rounded-2xl bg-white p-5 ring-1 ring-zinc-200"
        >
          <h2 className="text-lg font-semibold">Haitalliset toimijat nyt</h2>
          {o.actors.length === 0 ? (
            <p className="text-sm text-zinc-700">Ei haitallisia toimijoita.</p>
          ) : (
            <ul>
              {o.actors.map((a) => (
                <li key={a.id} className="border-t border-zinc-100 first:border-0">
                  <button
                    onClick={() => (a.kind === "ip" ? onPick(a.id) : goSessions())}
                    className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 py-3 text-left hover:bg-zinc-50"
                  >
                    <span className="flex min-w-0 flex-[999_1_300px] flex-col">
                      <span className="font-semibold">{a.title}</span>
                      <span className="truncate text-sm text-zinc-600">{a.detail}</span>
                    </span>
                    <ActionChip action={a.action} text={a.action_text} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-zinc-600">
            Toimenpiteet: Seuraa → Rajoita → Haaste → Estä. Bouncer suosittelee, se ei estä itse.
          </p>
        </section>
        <section
          aria-label="Luotettavuus"
          className="flex min-w-0 flex-[1_1_280px] flex-col gap-3 rounded-2xl bg-white p-5 ring-1 ring-zinc-200"
        >
          <h2 className="text-lg font-semibold">Kuinka usein olemme väärässä</h2>
          <div className="flex flex-col gap-1 rounded-xl bg-zinc-100 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-zinc-600">
              {h.synthetic ? "Simuloitu ajo" : "Labeloitu liikenne"}
            </p>
            {h.n_humans === 0 ? (
              <p className="text-sm">Ei labeloituja ihmisiä vielä.</p>
            ) : (
              <>
                <p className="text-2xl font-bold">
                  {h.false_alarms} / {h.n_humans} ihmistä
                </p>
                <p className="text-sm leading-relaxed text-zinc-800">
                  merkittiin botiksi. Otos on pieni: todellinen osuus voi olla jopa{" "}
                  {Math.round((h.fpr_ci95_upper ?? 0) * 100)} % (95 % yläraja).
                </p>
              </>
            )}
          </div>
          <p className="text-sm leading-relaxed text-zinc-700">
            Tavoite: alle 1 % väärät hälytykset ihmisille. Väite vaatii noin 300 ihmissessiota oikeasta
            liikenteestä.
          </p>
        </section>
      </div>
    </div>
  );
}
