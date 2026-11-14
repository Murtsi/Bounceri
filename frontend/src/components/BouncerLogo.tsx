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

/** Pomppiva logo + liukuva lime-viiva. */
function Loader({ message }: { message: string }) {
  return (
    <>
      <BouncerLogo mode="loop" className="text-6xl" />
      <div className="h-0.5 w-40 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
        <div className="sweep h-full w-2/5 rounded-full bg-primary" />
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
    </>
  );
}

export function SplashScreen({ message = "Ladataan…" }: { message?: string }) {
  return (
    <div role="status" className="flex min-h-[60vh] flex-col items-center justify-center gap-5">
      <Loader message={message} />
    </div>
  );
}

/** Koko näytön avausruutu: näkyy kunnes data on tullut, häivytetään pois. */
export function SplashOverlay({ leaving }: { leaving: boolean }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed inset-0 z-50 flex flex-col items-center justify-center gap-5 bg-background/70 backdrop-blur-2xl",
        leaving && "splash-out",
      )}
    >
      <Loader message="Analysoidaan liikennettä…" />
    </div>
  );
}
