import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/**
 * Syvyyspaneeli: kallistuu hiiren mukaan muutaman asteen ja heijastaa valon
 * osoittimen kohdalta. Arvot kirjoitetaan CSS-muuttujiin suoraan (ei uudelleenrenderöintiä).
 * Kosketus ja vähennetty liike: ei kallistusta.
 */
export function DepthPanel({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse" || reduced()) return;
    const el = ref.current!;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    el.style.setProperty("--rx", `${((0.5 - y) * 3).toFixed(2)}deg`);
    el.style.setProperty("--ry", `${((x - 0.5) * 4).toFixed(2)}deg`);
    el.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
    el.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
  };
  const onLeave = () => {
    const el = ref.current!;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  };
  return (
    <div className="depth-stage">
      <div ref={ref} className={cn("depth-panel", className)} onPointerMove={onMove} onPointerLeave={onLeave}>
        {children}
      </div>
    </div>
  );
}

/**
 * Perspektiivissä etenevä lattiaruudukko yleiskuvan taustalla: liike kohti katsojaa
 * kuin saapuva liikenne. Pelkkä tunnelma, ei dataa. Pysähtyy, kun ei näkyvissä.
 */
export function DepthFloor() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => el.classList.toggle("is-paused", !e.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className="depth-floor" aria-hidden="true">
      <div className="depth-floor-plane" />
      <div className="depth-horizon" />
    </div>
  );
}
