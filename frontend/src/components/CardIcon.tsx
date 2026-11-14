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

/** Kortin otsikkorivi: kuvake + otsikko + kuvaus. */
export function CardHeading({
  Icon,
  title,
  description,
}: {
  Icon: LucideIcon;
  title: React.ReactNode;
  description?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3">
      <CardIcon Icon={Icon} />
      <div className="min-w-0">
        <h2 className="text-base leading-tight font-semibold">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
    </div>
  );
}
