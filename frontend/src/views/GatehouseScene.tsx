import "./GatehouseScene.css";
import { useQuery } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api, type Label } from "@/api";

/*
 * Etusivun näyteikkuna: lasinen porttikoppi, jonka oven edessä seisoo portsari.
 * Jokainen piste on yksi oikea sessio sellaisena kuin Bouncer sen luokitteli:
 *   haitallinen botti    → punainen, pysähtyy portsarin käteen
 *   ihminen / hyvä botti → vihreä, kulkee ovesta läpi ja ulos takaa
 *   epävarma             → harmaa, pysähtyy hetkeksi tarkistukseen ja pääsee sisään
 * Uudet sessiot tulevat API:sta (2 s välein). Jos uusia ei tule, näkymä toistaa
 * viimeisimmät sessiot ja kertoo sen. Bouncer ei estä liikennettä: "pysähtyy" on
 * kuvitus suosituksesta, ei esto.
 *
 * Toteutus: CSS-3D (preserve-3d). Maa on XY-taso, seinät nousevat pystyyn
 * rotateX(-90deg):llä. Varjot yhdestä valosta (vasemmalta takaa ylhäältä).
 * Kävelijöiden sijainnit päivitetään requestAnimationFramella suoraan DOMiin.
 */

const W = 640;
const D = 420;
const BOX = { x: 250, y: 130, w: 200, d: 160, h: 140 };
const DOOR = { x: 324, w: 52, h: 92 };
const FIGURE = { x: 336, y: 320, w: 46, h: 78 };
const LIGHT = { x: 0.45, y: 0.28 };

type Kind = "stop" | "pass" | "check";

/** Reitit maan koordinaateissa. Punaiset päättyvät portsarin käteen (318, 324). */
const STOP_ROUTES = [
  "M -24 404 C 116 398 232 352 318 324",
  "M -24 318 C 96 326 226 330 318 324",
  "M 70 450 C 150 412 252 360 318 324",
];
/** Vihreät: oikealta edestä ovesta sisään, takaovesta ulos ja kaarella vasemmalle taakse. */
const PASS_ROUTES = [
  "M 664 414 C 520 406 404 360 366 328 L 366 104 C 366 62 300 44 -24 34",
  "M 664 352 C 540 350 420 342 372 324 L 372 100 C 372 54 322 28 -24 14",
  "M 600 450 C 500 424 402 374 361 332 L 361 108 C 361 72 282 62 -24 60",
];
const routesOf = (k: Kind) => (k === "stop" ? STOP_ROUTES : PASS_ROUTES);
const routeId = (k: Kind, i: number) => `${k === "stop" ? "stop" : "pass"}-${i}`;

const KIND_OF: Record<Label, Kind> = { bad_bot: "stop", human: "pass", good_bot: "pass", uncertain: "check" };
const SPEED = 118; // maan pikseleitä sekunnissa: rauhallinen kävely
const TRAIL = 46;
const MAX_ACTIVE = 14;
const SPAWN_GAP_MS = 520;
const HOLD_MS = 1300; // punainen odottaa portsarin edessä
const CHECK_MS = 750; // harmaa tarkistetaan oven edessä
const REPLAY_N = 12;
const LIVE_WINDOW_MS = 30_000;
const INTRO_MS = 2100; // saapumisanimaation kesto ennen ensimmäistä kävelijää

/** Pystyseinä: ulompi sijoittaa (siirto + suunta), sisempi nousee pystyyn. */
function Wall({
  x,
  y,
  deg,
  width,
  height,
  className,
  delay,
  children,
}: {
  x: number;
  y: number;
  deg: number;
  width: number;
  height: number;
  className?: string;
  delay: number;
  children?: ReactNode;
}) {
  return (
    <div
      className={`gh-wall ${className ?? ""}`}
      style={{
        width,
        height,
        transformOrigin: `0 ${height}px`,
        transform: `translate3d(${x}px, ${y - height}px, 0) rotateZ(${deg}deg)`,
      }}
    >
      <div className="gh-wall-face" style={{ "--gh-delay": `${delay}ms` } as CSSProperties}>
        {children}
      </div>
    </div>
  );
}

function DoorWall({ width, height, doorX }: { width: number; height: number; doorX: number }) {
  const d = `M0 0H${width}V${height}H0Z M${doorX} ${height - DOOR.h}H${doorX + DOOR.w}V${height}H${doorX}Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={d} fillRule="evenodd" className="gh-glass" />
      <path d={`M${doorX} ${height}V${height - DOOR.h}H${doorX + DOOR.w}V${height}`} className="gh-frame" />
      <path d={`M0 1.5H${width}`} className="gh-rim" />
    </svg>
  );
}

function PlainWall({ width, height }: { width: number; height: number }) {
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <rect width={width} height={height} className="gh-glass" />
      <path d={`M0 1.5H${width}`} className="gh-rim" />
    </svg>
  );
}

function Bouncer() {
  return (
    <svg viewBox="0 0 46 78" width={FIGURE.w} height={FIGURE.h} aria-hidden="true" className="gh-figure-art">
      <path d="M17 52 16 77M29 52 30 77" className="gh-leg" />
      <path d="M10 30Q23 22 36 30L34 56H12Z" className="gh-suit" />
      <path d="M19 27 23 34 27 27" className="gh-collar" />
      <path d="M35 32 38 50" className="gh-arm" />
      <g className="gh-stop-arm">
        <path d="M11 32 2 40" className="gh-arm" />
        <circle cx="1.5" cy="40.5" r="3.2" className="gh-hand" />
      </g>
      <circle cx="23" cy="16" r="8" className="gh-skin" />
      <path d="M15.5 14Q16 6 23 7Q30 7 30.5 14Q26 10.5 15.5 14Z" className="gh-hair" />
      <circle cx="30.6" cy="17" r="1.6" className="gh-earpiece" />
    </svg>
  );
}

type Walker = { key: number; kind: Kind; route: number };
type Motion = {
  kind: Kind;
  route: string;
  s: number;
  len: number;
  phase: "walk" | "hold" | "check" | "fade";
  until: number;
  checkAt: number;
  opacity: number;
  head?: SVGCircleElement | null;
  halo?: SVGCircleElement | null;
  trail?: SVGPathElement | null;
  ring?: SVGCircleElement | null;
};

export type GateMode = "live" | "replay" | "idle";

const prefersReduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

export function GatehouseScene({ onMode }: { onMode?: (m: GateMode) => void }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const figureRef = useRef<HTMLDivElement>(null);
  const spillRef = useRef<SVGEllipseElement>(null);
  const measure = useRef<Record<string, SVGPathElement | null>>({});
  const [scale, setScale] = useState(1);
  const [tilt, setTilt] = useState({ yaw: 0, pitch: 0 });
  const [paused, setPaused] = useState(false);
  const [offscreen, setOffscreen] = useState(false);
  const [walkers, setWalkers] = useState<Walker[]>([]);
  const [reduced] = useState(prefersReduced);
  const [mode, setMode] = useState<GateMode>("idle");

  const motion = useRef(new Map<number, Motion>());
  const queue = useRef<Kind[]>([]);
  const seen = useRef<Set<string> | null>(null);
  const recent = useRef<Kind[]>([]);
  const lastLive = useRef(-Infinity);
  const nextKey = useRef(1);
  const routePick = useRef(0);
  const started = useRef(performance.now());
  const running = !paused && !offscreen && !reduced;

  const { data: sessions } = useQuery({ queryKey: ["sessions", "gate", 80], queryFn: () => api.sessions(80) });

  // Uudet sessiot jonoon; ensimmäisellä kerralla viimeisimmät toistona.
  useEffect(() => {
    if (!sessions) return;
    const ordered = [...sessions].sort((a, b) => (a.started_at < b.started_at ? -1 : 1));
    recent.current = ordered.slice(-REPLAY_N).map((r) => KIND_OF[r.label]);
    if (seen.current === null) {
      seen.current = new Set(ordered.map((r) => r.id));
      queue.current.push(...recent.current);
      return;
    }
    const fresh = ordered.filter((r) => !seen.current!.has(r.id));
    fresh.forEach((r) => seen.current!.add(r.id));
    if (fresh.length) {
      lastLive.current = performance.now();
      queue.current.push(...fresh.map((r) => KIND_OF[r.label]));
      // Ruuhkassa näytetään uusimmat: jono ei kasva loputtomiin.
      if (queue.current.length > 30) queue.current.splice(0, queue.current.length - 30);
    }
  }, [sessions]);

  // Tila: live, kun uusia sessioita on tullut äskettäin; muuten toisto.
  useEffect(() => {
    const t = setInterval(() => {
      setMode(
        performance.now() - lastLive.current < LIVE_WINDOW_MS ? "live" : recent.current.length ? "replay" : "idle",
      );
    }, 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => onMode?.(reduced ? "idle" : mode), [mode, onMode, reduced]);

  // Mitoitus säiliöön.
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      setScale(Math.min(1.3, width / 620, height / 320));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Pysähtyy näkymän ulkopuolella ja taustavälilehdellä.
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    let visible = true;
    const sync = () => setOffscreen(!visible || document.hidden);
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      sync();
    });
    io.observe(el);
    document.addEventListener("visibilitychange", sync);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", sync);
    };
  }, []);

  // Animaatiosilmukka.
  useEffect(() => {
    if (!running) return;
    let raf = 0;
    let last = performance.now();
    let lastSpawn = 0;
    let idleSince = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const introDone = now - started.current > INTRO_MS;

      if (introDone && queue.current.length && motion.current.size < MAX_ACTIVE && now - lastSpawn > SPAWN_GAP_MS) {
        const kind = queue.current.shift()!;
        const i = routePick.current++ % routesOf(kind).length;
        const route = routeId(kind, i);
        const path = measure.current[route];
        const len = path?.getTotalLength() ?? 600;
        let checkAt = Infinity;
        if (kind === "check" && path) {
          // Tarkistuspiste: kohta, jossa reitti saapuu oven eteen.
          for (let s = 0; s < len; s += 4)
            if (path.getPointAtLength(s).y < 342) {
              checkAt = s;
              break;
            }
        }
        const key = nextKey.current++;
        motion.current.set(key, { kind, route, s: 0, len, phase: "walk", until: 0, checkAt, opacity: 0 });
        setWalkers((w) => [...w, { key, kind, route: i }]);
        lastSpawn = now;
      }
      // Kun uutta liikennettä ei tule, viimeisimmät sessiot toistetaan.
      if (introDone && !queue.current.length && motion.current.size === 0) {
        if (!idleSince) idleSince = now;
        if (now - idleSince > 2200 && recent.current.length) {
          queue.current.push(...recent.current);
          idleSince = 0;
        }
      } else idleSince = 0;

      let stopping = false;
      let doorGlow = 0;
      const done: number[] = [];
      for (const [key, m] of motion.current) {
        const path = measure.current[m.route];
        if (!path || !m.head || !m.trail) continue;
        if (m.phase === "walk") {
          m.s += SPEED * dt;
          m.opacity = Math.min(1, m.opacity + dt * 3);
          if (m.s >= m.checkAt) {
            m.s = m.checkAt;
            m.checkAt = Infinity;
            m.phase = "check";
            m.until = now + CHECK_MS;
          } else if (m.s >= m.len) {
            m.s = m.len;
            if (m.kind === "stop") {
              m.phase = "hold";
              m.until = now + HOLD_MS;
              m.ring?.classList.add("is-on");
            } else m.phase = "fade";
          }
        } else if (m.phase === "check") {
          if (now > m.until) m.phase = "walk";
        } else if (m.phase === "hold") {
          if (now > m.until) m.phase = "fade";
        } else {
          m.opacity -= dt * 1.6;
          if (m.opacity <= 0) done.push(key);
        }
        if (m.kind === "stop" && m.phase !== "fade" && m.len - m.s < 70) stopping = true;

        const p = path.getPointAtLength(m.s);
        const o = Math.max(0, m.opacity);
        for (const c of [m.head, m.halo]) {
          if (!c) continue;
          c.setAttribute("cx", p.x.toFixed(1));
          c.setAttribute("cy", p.y.toFixed(1));
          c.style.opacity = String(o);
        }
        m.trail.style.strokeDashoffset = String(-(m.s - TRAIL));
        m.trail.style.opacity = String(o * (m.phase === "walk" ? 1 : 0.35));
        // Ovi valaistuu, kun joku kulkee siitä.
        const dd = Math.hypot(p.x - (DOOR.x + DOOR.w / 2), p.y - BOX.y - BOX.d);
        doorGlow = Math.max(doorGlow, Math.max(0, 1 - dd / 70) * o);
      }
      figureRef.current?.classList.toggle("is-stopping", stopping);
      if (spillRef.current) spillRef.current.style.opacity = String(0.5 + doorGlow * 0.5);
      if (done.length) {
        done.forEach((k) => motion.current.delete(k));
        setWalkers((w) => w.filter((x) => !done.includes(x.key)));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running]);

  const onMove = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse" || reduced) return;
    const r = e.currentTarget.getBoundingClientRect();
    setTilt({ yaw: ((e.clientX - r.left) / r.width - 0.5) * 14, pitch: ((e.clientY - r.top) / r.height - 0.5) * -8 });
  };

  const attach = (key: number, part: "head" | "halo" | "trail" | "ring") => (el: SVGElement | null) => {
    const m = motion.current.get(key);
    if (m && el) (m as unknown as Record<string, SVGElement>)[part] = el;
  };

  const boxShadow = [
    [BOX.x, BOX.y],
    [BOX.x + BOX.w, BOX.y],
    [BOX.x + BOX.w + BOX.h * LIGHT.x, BOX.y + BOX.h * LIGHT.y],
    [BOX.x + BOX.w + BOX.h * LIGHT.x, BOX.y + BOX.d + BOX.h * LIGHT.y],
    [BOX.x + BOX.h * LIGHT.x, BOX.y + BOX.d + BOX.h * LIGHT.y],
    [BOX.x, BOX.y + BOX.d],
  ]
    .map((p) => p.join(","))
    .join(" ");
  const figLen = Math.hypot(FIGURE.h * LIGHT.x, FIGURE.h * LIGHT.y);
  const figAngle = (Math.atan2(LIGHT.y, LIGHT.x) * 180) / Math.PI;
  const fsx = FIGURE.x + (FIGURE.h * LIGHT.x) / 2;
  const fsy = FIGURE.y + (FIGURE.h * LIGHT.y) / 2;

  const style = {
    "--gh-scale": scale,
    "--gh-yaw": `${-28 + tilt.yaw}deg`,
    "--gh-pitch": `${57 + tilt.pitch}deg`,
  } as CSSProperties;

  return (
    <div className={`gh${running ? "" : " is-paused"}${reduced ? " is-reduced" : ""}`}>
      <div
        ref={stageRef}
        className="gh-stage"
        style={style}
        onPointerMove={onMove}
        onPointerLeave={() => setTilt({ yaw: 0, pitch: 0 })}
        role="img"
        aria-label="Animated illustration: a doorman stands in front of a glass gatehouse. Each moving dot is a recent session: bad bots stop at the doorman, humans and good bots walk through the doorway and out the other side, uncertain sessions pause to be checked."
      >
        <div className="gh-world" style={{ width: W, height: D }}>
          <svg className="gh-ground" width={W} height={D} viewBox={`0 0 ${W} ${D}`} aria-hidden="true">
            <defs>
              <radialGradient id="gh-floor-glow" cx="52%" cy="58%" r="58%">
                <stop offset="0" stopColor="#c5ef5d" stopOpacity=".1" />
                <stop offset="1" stopColor="#c5ef5d" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="gh-spill" cx="50%" cy="0%" r="100%">
                <stop offset="0" stopColor="#e4ff9a" stopOpacity=".45" />
                <stop offset=".55" stopColor="#c5ef5d" stopOpacity=".1" />
                <stop offset="1" stopColor="#c5ef5d" stopOpacity="0" />
              </radialGradient>
              <filter id="gh-soft" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="5" />
              </filter>
              <filter id="gh-softer" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2.4" />
              </filter>
              <filter id="gh-glow" x="-200%" y="-200%" width="500%" height="500%">
                <feGaussianBlur stdDeviation="3.2" />
              </filter>
            </defs>
            <ellipse cx={W / 2} cy={D / 2 + 20} rx={W * 0.52} ry={D * 0.5} fill="url(#gh-floor-glow)" />
            <g className="gh-shadows">
              <polygon points={boxShadow} className="gh-shadow" filter="url(#gh-soft)" />
              <ellipse
                cx={fsx}
                cy={fsy}
                rx={figLen / 2 + 7}
                ry={7}
                transform={`rotate(${figAngle} ${fsx} ${fsy})`}
                className="gh-shadow gh-shadow-figure"
                filter="url(#gh-softer)"
              />
            </g>
            {/* Ovesta lankeava hehku: ei luo varjoja, voimistuu kun joku kulkee ovesta. */}
            <ellipse
              ref={spillRef}
              cx={DOOR.x + DOOR.w / 2}
              cy={BOX.y + BOX.d + 34}
              rx={58}
              ry={40}
              fill="url(#gh-spill)"
              className="gh-spill"
            />
            <ellipse cx={FIGURE.x} cy={FIGURE.y} rx={12} ry={4.5} className="gh-contact" filter="url(#gh-softer)" />

            <g className="gh-routes">
              {STOP_ROUTES.map((d, i) => (
                <path key={`s${i}`} d={d} pathLength={1} className="gh-route gh-route-stop" />
              ))}
              {PASS_ROUTES.map((d, i) => (
                <path key={`p${i}`} d={d} pathLength={1} className="gh-route gh-route-pass" />
              ))}
            </g>
            {/* Mittauspolut (näkymättömät, ilman pathLengthiä: oikeat pikselipituudet). */}
            <g className="gh-measure">
              {STOP_ROUTES.map((d, i) => (
                <path key={`ms${i}`} d={d} ref={(el) => void (measure.current[routeId("stop", i)] = el)} />
              ))}
              {PASS_ROUTES.map((d, i) => (
                <path key={`mp${i}`} d={d} ref={(el) => void (measure.current[routeId("pass", i)] = el)} />
              ))}
            </g>

            {walkers.map((w) => (
              <g key={w.key} className={`gh-walker gh-walker-${w.kind}`}>
                <path
                  d={routesOf(w.kind)[w.route]}
                  className="gh-trail"
                  style={{ strokeDasharray: `${TRAIL} 4000`, strokeDashoffset: TRAIL, opacity: 0 }}
                  ref={attach(w.key, "trail")}
                />
                <circle r={8} cx={-60} cy={-60} className="gh-halo" filter="url(#gh-glow)" style={{ opacity: 0 }} ref={attach(w.key, "halo")} />
                <circle r={3.6} cx={-60} cy={-60} className="gh-dot" style={{ opacity: 0 }} ref={attach(w.key, "head")} />
                {w.kind === "stop" && <circle cx={318} cy={324} r={9} className="gh-ring" ref={attach(w.key, "ring")} />}
              </g>
            ))}
          </svg>

          {/* Koppi: seinät nousevat saapuessa, katto laskeutuu. */}
          <Wall x={BOX.x + BOX.w} y={BOX.y} deg={180} width={BOX.w} height={BOX.h} className="gh-back" delay={200}>
            <DoorWall width={BOX.w} height={BOX.h} doorX={BOX.w - (DOOR.x - BOX.x) - DOOR.w} />
          </Wall>
          <Wall x={BOX.x} y={BOX.y} deg={90} width={BOX.d} height={BOX.h} className="gh-left" delay={330}>
            <PlainWall width={BOX.d} height={BOX.h} />
          </Wall>
          <Wall x={BOX.x + BOX.w} y={BOX.y + BOX.d} deg={-90} width={BOX.d} height={BOX.h} className="gh-right" delay={460}>
            <PlainWall width={BOX.d} height={BOX.h} />
          </Wall>
          <Wall x={BOX.x} y={BOX.y + BOX.d} deg={0} width={BOX.w} height={BOX.h} className="gh-front" delay={590}>
            <DoorWall width={BOX.w} height={BOX.h} doorX={DOOR.x - BOX.x} />
          </Wall>
          <div
            className="gh-roof"
            style={{ width: BOX.w, height: BOX.d, transform: `translate3d(${BOX.x}px, ${BOX.y}px, ${BOX.h}px)` }}
          >
            <div className="gh-roof-face" />
          </div>

          <div
            ref={figureRef}
            className="gh-figure"
            style={{
              width: FIGURE.w,
              height: FIGURE.h,
              transformOrigin: `${FIGURE.w / 2}px ${FIGURE.h}px`,
              transform: `translate3d(${FIGURE.x - FIGURE.w / 2}px, ${FIGURE.y - FIGURE.h}px, 0) rotateZ(calc(-1 * var(--gh-yaw)))`,
            }}
          >
            <div className="gh-figure-face">
              <div className="gh-figure-pop">
                <Bouncer />
              </div>
            </div>
          </div>
        </div>
      </div>
      {!reduced && (
        <button
          type="button"
          className="gh-toggle"
          onClick={() => setPaused((p) => !p)}
          aria-label={paused ? "Play the gatehouse animation" : "Pause the gatehouse animation"}
          title={paused ? "Play" : "Pause"}
        >
          {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
        </button>
      )}
    </div>
  );
}
