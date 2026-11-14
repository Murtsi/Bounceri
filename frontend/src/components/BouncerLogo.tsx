import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

const TAIL = "ouncer".split("");

type Mode = "play" | "loop" | "static";

/**
 * "Bouncer": B pysyy paikallaan, "ouncer" pomppaa siitä ulos kirjain kerrallaan.
 * play = kerran (otsikko), loop = toistuu (latausnäyttö), static = ei liikettä.
 * prefers-reduced-motion poistaa animaation (index.css).
 */
export function BouncerLogo({ mode = "play", className }: { mode?: Mode; className?: string }) {
  return (
    <span
      role="img"
      aria-label="Bouncer"
      className={cn(
        "inline-flex select-none items-baseline font-bold tracking-tight",
        mode === "play" && "bouncer-play",
        mode === "loop" && "bouncer-loop",
        mode === "static" && "bouncer-static",
        className,
      )}
    >
      <span aria-hidden="true" className="bouncer-b">
        B
      </span>
      {TAIL.map((ch, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="bouncer-letter"
          // Lähtöpiste = B:n kohta: sitä kauempana, mitä pidemmällä kirjain on.
          style={{ "--i": i, "--from": `${-(i + 1) * 0.6}em` } as CSSProperties}
        >
          {ch}
        </span>
      ))}
    </span>
  );
}

export function SplashScreen({ message = "Ladataan…" }: { message?: string }) {
  return (
    <div role="status" className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <BouncerLogo mode="loop" className="text-6xl" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
