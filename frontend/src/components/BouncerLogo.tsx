import { cn } from "@/lib/utils";

type Mode = "play" | "static";

/**
 * "Bouncer": B:n alakaari painuu sisään kuin jousi ja ponnauttaa loppusanan "ouncer" ulos,
 * joka pomppii paikalleen kuin pallo.
 * play = liike kerran, sana jää näkyviin; static = valmis logo ilman liikettä.
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
        mode === "static" && "bouncer-static",
        className,
      )}
    >
      {/* B piirrettynä: varsi + yläkaari + alakaari erikseen, jotta alakaari voi painua sisään. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 62 72"
        className="bouncer-b relative z-10 mr-[0.04em] h-[0.72em] w-[0.62em] shrink-0 overflow-visible"
        fill="none"
        stroke="currentColor"
        strokeWidth="14"
      >
        <path d="M7 0V72" />
        <path d="M7 7H33A14 14 0 0 1 33 35H7" />
        <g className="bouncer-bowl">
          {/* non-scaling-stroke: viiva pysyy saman paksuisena, vaikka kaari puristuu kasaan. */}
          <path d="M7 35H37A15 15 0 0 1 37 65H7" vectorEffect="non-scaling-stroke" style={{ strokeWidth: "0.14em" }} />
        </g>
      </svg>
      {/* "ouncer" yhtenä sanana: syntyy B:n alakaaresta ja pomppii paikalleen. */}
      <span aria-hidden="true" className="bouncer-tail">
        ouncer
      </span>
    </span>
  );
}

/** Logo ponnahtaa kerran + liukuva lime-viiva kertoo, että ladataan. */
function Loader({ message }: { message: string }) {
  return (
    <>
      <BouncerLogo mode="play" className="text-6xl" />
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
