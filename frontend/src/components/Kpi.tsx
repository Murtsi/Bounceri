import type { LucideIcon } from "lucide-react";
import type { CSSProperties } from "react";
import { CardIcon } from "@/components/CardIcon";
import { Card } from "@/components/ui/card";
import { useCountUp } from "@/lib/useCountUp";
import { cn } from "@/lib/utils";

/**
 * Minipylväät tunnusluvun alla: sama aikasarja kuin pääkaaviossa, ilman akseleita.
 * Väri kertoo sarjan (dataviz: sama väri = sama asia kaikkialla).
 */
function Sparkbars({ values, color, hatch }: { values: number[]; color: string; hatch?: boolean }) {
  const max = Math.max(1, ...values);
  return (
    <div aria-hidden="true" className="flex h-9 items-end gap-[2px]">
      {values.map((v, i) => (
        <span
          key={i}
          className={cn("bar-grow flex-1 rounded-t-[2px]", hatch && v > 0 && "hatch")}
          style={
            {
              height: `${Math.max(v > 0 ? 12 : 4, (v / max) * 100)}%`,
              background: hatch && v > 0 ? undefined : v > 0 ? color : "rgba(255,255,255,0.06)",
              "--i": i,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}

export function Kpi({
  Icon,
  label,
  value,
  suffix,
  note,
  spark,
  color = "var(--foreground)",
  delay = 0,
  accent = false,
}: {
  Icon: LucideIcon;
  label: string;
  value: number;
  suffix?: string;
  note?: string;
  spark?: number[];
  color?: string;
  delay?: number;
  accent?: boolean;
}) {
  const shown = useCountUp(value);
  return (
    <Card className="rise min-w-0 gap-3 px-4 py-4 sm:px-5 sm:py-5" style={{ "--d": `${delay}ms` } as CSSProperties}>
      <div className="flex items-center gap-3">
        <CardIcon Icon={Icon} className={cn(accent && "border-primary/40 bg-primary/15 text-primary")} />
        <p className="truncate text-sm text-muted-foreground">{label}</p>
      </div>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums tracking-tight sm:text-3xl">
            {shown.toLocaleString("en-GB")}
            {suffix && <span className="ml-0.5 text-lg text-muted-foreground">{suffix}</span>}
          </p>
          {note && <p className="mt-0.5 truncate text-xs text-muted-foreground">{note}</p>}
        </div>
        {spark && spark.length > 0 && (
          <div className="hidden w-24 shrink-0 sm:block">
            <Sparkbars values={spark} color={color} />
          </div>
        )}
      </div>
    </Card>
  );
}
