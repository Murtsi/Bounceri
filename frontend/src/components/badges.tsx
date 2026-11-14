import { Ban, Eye, Gauge, ShieldQuestion } from "lucide-react";
import type { ComponentType } from "react";
import { ACTION_TEXT, LABEL_TEXT, type Action, type Label } from "@/api";
import { Swatch } from "@/components/charts";
import { Badge } from "@/components/ui/badge";

/** Luokka: väri tulee ruudusta, teksti pysyy tekstivärissä (dataviz). */
export function LabelBadge({ label }: { label: Label }) {
  return (
    <Badge variant="outline" className="gap-1.5 font-medium">
      <Swatch label={label} />
      {LABEL_TEXT[label]}
    </Badge>
  );
}

/** Toimenpide: tilaväri vain kuvakkeessa, aina kuvake + teksti. */
const ACTION_ICON: Record<Exclude<Action, "none">, { Icon: ComponentType<{ className?: string }>; color: string }> = {
  block: { Icon: Ban, color: "var(--status-critical)" },
  rate_limit: { Icon: Gauge, color: "var(--status-serious)" },
  challenge: { Icon: ShieldQuestion, color: "var(--status-warning)" },
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
