import { useEffect, useRef, useState } from "react";

const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** Luku liukuu edellisestä arvosta uuteen (ease-out). Vähennetty liike → heti perille. */
export function useCountUp(target: number, ms = 700): number {
  const [value, setValue] = useState(reduced() ? target : 0);
  const from = useRef(value);
  useEffect(() => {
    if (reduced()) {
      setValue(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const v = a + (target - a) * (1 - (1 - t) ** 3);
      setValue(v);
      from.current = v;
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return Math.round(value);
}
