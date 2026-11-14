import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Pieni lasipallo kuvakkeelle korttien otsikoissa (sama kieli kuin sivupalkissa). */
export function CardIcon({ Icon, className }: { Icon: LucideIcon; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full border bg-white/[0.06] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]",
        className,
      )}
    >
      <Icon className="size-4" />
    </span>
  );
}

/**
 * Kortin otsikko: pelkkä typografia. Kuvakepallo jokaisen otsikon edessä oli
 * geneerinen kuvio; `Icon` säilyy rajapinnassa, mutta sitä ei piirretä.
 */
export function CardHeading({
  title,
  description,
}: {
  Icon?: LucideIcon;
  title: React.ReactNode;
  description?: React.ReactNode;
}) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}
