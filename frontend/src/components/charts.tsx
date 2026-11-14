import { useState, type CSSProperties } from "react";
import { ChartColumn, Table2 } from "lucide-react";
import { LABEL_TEXT, type Label } from "@/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCountUp } from "@/lib/useCountUp";
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

const GAP = "gap-[3px]";

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
  const shown = useCountUp(sum);
  // Aika-akselille noin 4 merkintää tasaisin välein: vähemmän tekstiä, ei törmäyksiä.
  const every = Math.max(1, Math.ceil(rows.length / 4));
  const ticks = new Set(rows.map((_, i) => i).filter((i) => (rows.length - 1 - i) % every === 0));

  return (
    <figure className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-3xl font-semibold tabular-nums tracking-tight">{shown.toLocaleString("fi-FI")}</p>
          <figcaption className="text-xs text-muted-foreground">
            pyyntöä · {unit} välein{peak && peak.n > 0 ? ` · huippu ${peak.n} klo ${peak.label}` : ""}
          </figcaption>
        </div>
        <Button
          variant="outline"
          size="icon"
          className="self-start"
          onClick={() => setTable((v) => !v)}
          aria-pressed={table}
          aria-label={table ? "Näytä kaaviona" : "Näytä taulukkona"}
          title={table ? "Näytä kaaviona" : "Näytä taulukkona"}
        >
          {table ? <ChartColumn /> : <Table2 />}
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
                    "flex h-full w-full flex-col justify-end overflow-hidden rounded-t-[4px] transition-colors",
                    hover === i ? "bg-white/[0.08]" : "bg-white/[0.03]",
                  )}
                >
                  {n > 0 && (
                    // Yläpää pyöreä, pohja suora (dataviz: pyöristys vain datan päähän).
                    <div
                      className="bar-grow flex flex-col-reverse gap-[2px] overflow-hidden rounded-t-[4px] transition-[height] duration-500"
                      style={{ height: `${(n / max) * 100}%`, minHeight: 6, "--i": i } as CSSProperties}
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
              <span key={p.t} className="relative flex-1 overflow-visible whitespace-nowrap text-center">
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
      <div role="img" aria-label={label} className="fill-x flex h-7 gap-0.5 overflow-hidden rounded-full">
        {parts.map((l) => {
          const p = pct(counts[l], total);
          const f = fill(l);
          return (
            <div
              key={l}
              className={cn(
                "flex items-center px-3 text-xs font-semibold text-[#0f1a0c] transition-[width] duration-500",
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
