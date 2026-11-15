import { Ban, Eye, Gauge, ShieldQuestion } from "lucide-react";
import type { ComponentType } from "react";
import { ACTION_TEXT, LABEL_TEXT, type Action, type Activity, type Label } from "@/api";
import { SERIES_VAR } from "@/components/charts";
import { Badge } from "@/components/ui/badge";

const ACTIVITY_TEXT: Record<Activity, string> = {
  browser_like: "Browser-like",
  automation_signal: "Automation signal",
  insufficient_evidence: "Needs more evidence",
};
const ACTIVITY_COLOR: Record<Activity, string> = {
  browser_like: "var(--activity-browser)",
  automation_signal: "var(--activity-automation)",
  insufficient_evidence: "var(--series-uncertain)",
};

export function LabelBadge({ label, activity }: { label: Label; activity?: Activity | null }) {
  const observation = label === "uncertain" && activity ? ACTIVITY_TEXT[activity] : null;
  const color = observation && activity ? ACTIVITY_COLOR[activity] : SERIES_VAR[label];
  return (
    <Badge variant="outline" className="gap-1.5 font-medium"
      style={{ color, borderColor: `color-mix(in srgb, ${color} 45%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)` }}
      title={observation ? `${observation}; human/bot classification remains uncertain.` : undefined}>
      <span aria-hidden="true" className="size-2 rounded-sm" style={{ backgroundColor: color }} />
      {observation ?? LABEL_TEXT[label]}
    </Badge>
  );
}

/** Toimenpide: erotetaan kuvakkeen muodolla + tekstillä, ei värillä (rauhallinen lasi-UI). */
const ACTION_ICON: Record<Exclude<Action, "none">, { Icon: ComponentType<{ className?: string }>; color: string }> = {
  block: { Icon: Ban, color: "var(--foreground)" },
  rate_limit: { Icon: Gauge, color: "var(--foreground)" },
  challenge: { Icon: ShieldQuestion, color: "var(--muted-foreground)" },
  monitor: { Icon: Eye, color: "var(--muted-foreground)" },
};

export function ActionBadge({ action }: { action: Action | null | undefined }) {
  if (!action || action === "none") return <span className="text-muted-foreground">—</span>;
  const { Icon, color } = ACTION_ICON[action];
  return (
    <Badge variant="outline" className="gap-1.5 font-semibold">
      <span style={{ color }}>
        <Icon className="size-3.5" />
      </span>
      {ACTION_TEXT[action]}
    </Badge>
  );
}
