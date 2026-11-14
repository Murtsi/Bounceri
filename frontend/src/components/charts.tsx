import { useState, type CSSProperties } from "react";
import { LABEL_TEXT, type Label } from "@/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/** Pinoamisjärjestys = validoitu viereisyysjärjestys (dataviz). Alhaalta ylös. */
export const SERIES: Label[] = ["human", "good_bot", "bad_bot", "uncertain"];
export const SERIES_VAR: Record<Label, string> = {
  human: "var(--series-human)",
  good_bot: "var(--series-good)",
  bad_bot: "var(--series-bad)",
  uncertain: "var(--series-uncertain)",
};

/** Sarjan täyttö: "epävarma" = harmaa + vinoviivoitus (tekstuuri), muut tasaväri. */
function fill(label: Label): { className: string; style: CSSProperties } {
  return label === "uncertain"
    ? { className: "hatch", style: {} }
    : { className: "", style: { background: SERIES_VAR[label] } };
}

export function Swatch({ label, className }: { label: Label; className?: string }) {
  const f = fill(label);
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block size-2.5 shrink-0 rounded-[3px]", f.className, className)}
      style={f.style}
    />
  );
}

export function Legend({ counts }: { counts?: Partial<Record<Label, number>> }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {SERIES.map((l) => (
        <li key={l} className="flex items-center gap-1.5">
          <Swatch label={l} />
          <span className="text-foreground">{LABEL_TEXT[l]}</span>
          {counts && <span className="tabular-nums">{counts[l] ?? 0}</span>}
        </li>
      ))}
    </ul>
  );
}

type Point = { t: string } & Record<Label, number>;

function clock(iso: string, seconds: boolean) {
  return new Date(iso).toLocaleTimeString("fi-FI", {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
  });
}

const sumOf = (p: Point) => SERIES.reduce((s, l) => s + (p[l] ?? 0), 0);

function Tip({ p, label }: { p: Point; label: string }) {
  return (
    <div className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 min-w-40 -translate-x-1/2 rounded-2xl border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg backdrop-blur-xl">
      <p className="mb-1.5 font-medium">{label}</p>
      <ul className="flex flex-col gap-1">
        {[...SERIES].reverse().map((l) => (
          <li key={l} className="flex items-center gap-2">
            <Swatch label={l} />
            <span className="flex-1 text-muted-foreground">{LABEL_TEXT[l]}</span>
            <span className="tabular-nums">{p[l]}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 flex justify-between border-t pt-1.5 text-muted-foreground">
        <span>Yhteensä</span>
        <span className="tabular-nums text-foreground">{sumOf(p)}</span>
      </p>
    </div>
  );
}

const GAP = "gap-[clamp(3px,1.2vw,12px)]";

/**
 * Pyynnöt aikaväleittäin: ohuet pinotut pylväät himmeän "raidan" päällä
 * (widget-tyyli, ei y-akselia). Kokonaismäärä ja huippu luetaan otsikosta,
 * tarkat luvut vihjeestä tai taulukkonäkymästä.
 */
export function TrafficChart({ points, stepS }: { points: Point[]; stepS: number }) {
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const secs = stepS < 60;
  const rows = points.map((p) => ({ p, label: clock(p.t, secs), n: sumOf(p) }));
  const sum = rows.reduce((s, r) => s + r.n, 0);
  const max = Math.max(1, ...rows.map((r) => r.n));
  const peak = rows.find((r) => r.n === max);
  const unit = secs ? `${stepS} s` : `${stepS / 60} min`;
  // Aika-akselille vain alku, keskikohta ja loppu: vähemmän tekstiä, ei törmäyksiä.
  const ticks = new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1]);

  return (
    <figure className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-3xl font-semibold tabular-nums tracking-tight">{sum.toLocaleString("fi-FI")}</p>
          <figcaption className="text-xs text-muted-foreground">
            pyyntöä · {unit} välein{peak && peak.n > 0 ? ` · huippu ${peak.n} klo ${peak.label}` : ""}
          </figcaption>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setTable((v) => !v)} aria-pressed={table}>
          {table ? "Kaavio" : "Taulukko"}
        </Button>
      </div>

      {table ? (
        <div className="max-h-64 overflow-y-auto rounded-2xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Aika</TableHead>
                {SERIES.map((l) => (
                  <TableHead key={l} className="text-right">
                    {LABEL_TEXT[l]}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ p, label }) => (
                <TableRow key={p.t}>
                  <TableCell className="tabular-nums">{label}</TableCell>
                  {SERIES.map((l) => (
                    <TableCell key={l} className="text-right tabular-nums">
                      {p[l]}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div>
          <div
            role="img"
            aria-label={`Pinottu pylväskaavio: pyynnöt ${unit} väleissä luokittain, yhteensä ${sum}. Tarkat luvut taulukkonäkymässä.`}
            className={cn("flex h-48 items-stretch", GAP)}
            onMouseLeave={() => setHover(null)}
          >
            {rows.map(({ p, label, n }, i) => (
              <div key={p.t} className="relative flex flex-1 justify-center" onMouseEnter={() => setHover(i)}>
                {/* Raita: koko korkeus, himmeä — näyttää myös tyhjät välit. */}
                <div
                  className={cn(
                    "flex h-full w-full max-w-[18px] flex-col justify-end overflow-hidden rounded-full transition-colors",
                    hover === i ? "bg-white/[0.09]" : "bg-white/[0.045]",
                  )}
                >
                  {n > 0 && (
                    // Yläpää pyöreä, pohja suora (dataviz: pyöristys vain datan päähän).
                    <div
                      className="flex flex-col-reverse gap-[2px] overflow-hidden rounded-t-full"
                      style={{ height: `${(n / max) * 100}%`, minHeight: 6 }}
                    >
                      {SERIES.filter((l) => p[l] > 0).map((l) => {
                        const f = fill(l);
                        return (
                          <div
                            key={l}
                            className={cn("w-full shrink-0", f.className)}
                            style={{ ...f.style, flexGrow: p[l], flexBasis: 0, minHeight: 3 }}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
                {hover === i && <Tip p={p} label={label} />}
              </div>
            ))}
          </div>
          <div className={cn("mt-2 flex text-[11px] tabular-nums text-[color:var(--ink-muted)]", GAP)}>
            {rows.map(({ p, label }, i) => (
              <span key={p.t} className="flex-1 whitespace-nowrap text-center">
                {ticks.has(i) ? label : ""}
              </span>
            ))}
          </div>
        </div>
      )}
      <Legend />
    </figure>
  );
}

/** Yksi kokonaisuus osiin: tall segmented bar (28 px), osuus palkin sisällä jos mahtuu. */
export function SegmentedBar({ counts, total }: { counts: Record<Label, number>; total: number }) {
  const parts = SERIES.filter((l) => counts[l] > 0);
  const label = parts.map((l) => `${LABEL_TEXT[l]} ${counts[l]} (${pct(counts[l], total)} %)`).join(", ");
  return (
    <div className="flex flex-col gap-3">
      <div role="img" aria-label={label} className="flex h-7 gap-0.5">
        {parts.map((l) => {
          const p = pct(counts[l], total);
          const f = fill(l);
          return (
            <div
              key={l}
              className={cn(
                "flex items-center overflow-visible rounded-md px-2 text-xs font-semibold text-white",
                f.className,
              )}
              style={{ width: `${(counts[l] / total) * 100}%`, ...f.style }}
              title={`${LABEL_TEXT[l]}: ${counts[l]} (${p} %)`}
            >
              {p >= 12 ? `${p} %` : ""}
            </div>
          );
        })}
      </div>
      <Legend counts={counts} />
    </div>
  );
}

export function pct(n: number, total: number) {
  return total ? Math.round((n / total) * 100) : 0;
}
