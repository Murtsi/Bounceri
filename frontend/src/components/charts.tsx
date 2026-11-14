import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipContentProps } from "recharts";
import { LABEL_TEXT, type Label } from "@/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/** Pinoamisjärjestys = validoitu viereisyysjärjestys (dataviz: ΔE ≥ 9,2). */
export const SERIES: Label[] = ["human", "good_bot", "bad_bot", "uncertain"];
export const SERIES_VAR: Record<Label, string> = {
  human: "var(--series-human)",
  good_bot: "var(--series-good)",
  bad_bot: "var(--series-bad)",
  uncertain: "var(--series-uncertain)",
};

export function Swatch({ label, className }: { label: Label; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block size-2.5 shrink-0 rounded-[3px]", className)}
      style={{ background: SERIES_VAR[label] }}
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

function ChartTooltip({ active, payload, label }: TooltipContentProps<number, string>) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (Number(p.value) || 0), 0);
  return (
    <div className="min-w-40 rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="mb-1.5 font-medium">{label}</p>
      <ul className="flex flex-col gap-1">
        {[...payload].reverse().map((p) => (
          <li key={String(p.dataKey)} className="flex items-center gap-2">
            <Swatch label={p.dataKey as Label} />
            <span className="flex-1 text-muted-foreground">{LABEL_TEXT[p.dataKey as Label]}</span>
            <span className="tabular-nums">{p.value}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 flex justify-between border-t pt-1.5 text-muted-foreground">
        <span>Yhteensä</span>
        <span className="tabular-nums text-foreground">{total}</span>
      </p>
    </div>
  );
}

/** Pinottu pylväskaavio pyynnöistä aikaväleittäin + taulukkonäkymä (saavutettavuus). */
export function TrafficChart({ points, stepS }: { points: Point[]; stepS: number }) {
  const [table, setTable] = useState(false);
  const rows = points.map((p) => ({ ...p, label: clock(p.t, stepS < 60) }));
  const unit = stepS < 60 ? `${stepS} s` : `${stepS / 60} min`;
  return (
    <figure className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <figcaption className="text-xs text-muted-foreground">Pyyntöä / {unit}, luokiteltuna session mukaan</figcaption>
        <Button variant="ghost" size="sm" onClick={() => setTable((v) => !v)} aria-pressed={table}>
          {table ? "Kaavio" : "Taulukko"}
        </Button>
      </div>
      {table ? (
        <div className="max-h-64 overflow-y-auto rounded-md border">
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
              {rows.map((r) => (
                <TableRow key={r.t}>
                  <TableCell className="tabular-nums">{r.label}</TableCell>
                  {SERIES.map((l) => (
                    <TableCell key={l} className="text-right tabular-nums">
                      {r[l]}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        // Korkeus sisältää x-akselin, ettei kortti saa sisäkkäistä vierityspalkkia.
        <div className="h-60" role="img" aria-label={`Pinottu pylväskaavio: pyynnöt ${unit} väleissä luokittain`}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: -20 }} barCategoryGap="20%">
              <CartesianGrid vertical={false} stroke="var(--grid)" strokeWidth={1} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: "var(--axis)" }}
                tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
                interval="preserveStartEnd"
                minTickGap={28}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
              />
              <Tooltip content={ChartTooltip} cursor={{ fill: "var(--muted)", opacity: 0.6 }} />
              {SERIES.map((l, i) => (
                <Bar
                  key={l}
                  dataKey={l}
                  stackId="s"
                  fill={SERIES_VAR[l]}
                  maxBarSize={24}
                  // 2 px rako segmenttien välissä pinnan värillä (dataviz: surface gap).
                  stroke="var(--card)"
                  strokeWidth={2}
                  radius={i === SERIES.length - 1 ? [4, 4, 0, 0] : 0}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
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
          return (
            <div
              key={l}
              className="flex items-center overflow-visible rounded-[4px] px-2 text-xs font-semibold text-white"
              style={{ width: `${(counts[l] / total) * 100}%`, background: SERIES_VAR[l] }}
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
