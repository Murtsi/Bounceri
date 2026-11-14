import "./GatehouseScene.css";
import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/*
 * Kuvitus, ei mittari: lasinen porttikoppi (sisäänkäynti), jonka oven edessä
 * seisova portsari pysäyttää punaisen reitin. Vihreä reitti kulkee oviaukosta
 * läpi, kopin poikki ja ulos takaovesta. Seinät ovat himmeää lasia: kopin sisus
 * ja takaovi eivät kuulu läpi (ei "ikkunoita"), reitti katoaa ovesta ja palaa takaa.
 *
 * Toteutus: oikea CSS-3D-näkymä (preserve-3d). Maa on XY-taso; seinät nostetaan
 * pystyyn rotateX(-90deg):llä. Kaikki varjot lasketaan samasta valosta
 * (vasemmalta takaa ylhäältä → varjot osoittavat +x/+y), korkeuteen suhteutettuna.
 */

// Maan koordinaatit (px). Kamera katsoo +y-suunnasta.
const W = 640;
const D = 420;
const BOX = { x: 250, y: 130, w: 200, d: 160, h: 140 };
const DOOR = { x: 324, w: 52, h: 92 }; // sama aukko edessä ja takana
const FIGURE = { x: 336, y: 320, w: 46, h: 78 }; // jalkojen keskikohta oven edessä
/** Valon suunta: varjon siirtymä per korkeuspikseli. */
const LIGHT = { x: 0.45, y: 0.28 };

const RED_ROUTE = "M -24 404 C 116 398 232 352 318 324";
// Vihreä: oikealta edestä ovesta sisään, takaovesta ulos ja kaarella vasemmalle taakse.
const GREEN_ROUTE = "M 664 414 C 520 406 402 360 364 326 L 364 104 C 364 62 300 44 -24 34";

/** Pystyseinä, jonka alareuna on maassa pisteestä (x, y) suuntaan `deg`. */
function Wall({
  x,
  y,
  deg,
  width,
  height,
  className,
  children,
}: {
  x: number;
  y: number;
  deg: number;
  width: number;
  height: number;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={`gh-wall ${className ?? ""}`}
      style={{
        width,
        height,
        transformOrigin: `0 ${height}px`,
        transform: `translate3d(${x}px, ${y - height}px, 0) rotateZ(${deg}deg) rotateX(-90deg)`,
      }}
    >
      {children}
    </div>
  );
}

/** Seinä oviaukolla (evenodd): aukko on oikeasti tyhjä, reitti näkyy läpi. */
function DoorWall({ width, height, door }: { width: number; height: number; door: { x: number; w: number; h: number } }) {
  const d = `M0 0H${width}V${height}H0Z M${door.x} ${height - door.h}H${door.x + door.w}V${height}H${door.x}Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={d} fillRule="evenodd" className="gh-glass" />
      <path
        d={`M${door.x} ${height}V${height - door.h}H${door.x + door.w}V${height}`}
        className="gh-frame"
      />
    </svg>
  );
}

function PlainWall({ width, height }: { width: number; height: number }) {
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <rect width={width} height={height} className="gh-glass" />
    </svg>
  );
}

/** Portsari: pystytaso, joka käännetään aina kameraa kohti (billboard). */
function Bouncer() {
  return (
    <svg viewBox="0 0 46 78" width={FIGURE.w} height={FIGURE.h} aria-hidden="true" className="gh-figure-art">
      {/* jalat */}
      <path d="M17 52 16 77M29 52 30 77" className="gh-leg" />
      {/* vartalo: tumma puku */}
      <path d="M10 30Q23 22 36 30L34 56H12Z" className="gh-suit" />
      <path d="M19 27 23 34 27 27" className="gh-collar" />
      {/* vasen käsi (katsojan oikealla) levossa */}
      <path d="M35 32 38 50" className="gh-arm" />
      {/* oikea käsi (katsojan vasemmalla): nousee pysäytysmerkkiin */}
      <g className="gh-stop-arm">
        <path d="M11 32 2 40" className="gh-arm" />
        <circle cx="1.5" cy="40.5" r="3.2" className="gh-hand" />
      </g>
      {/* pää ja kuuloke */}
      <circle cx="23" cy="16" r="8" className="gh-head" />
      <path d="M15.5 14Q16 6 23 7Q30 7 30.5 14Q26 10.5 15.5 14Z" className="gh-hair" />
      <circle cx="30.6" cy="17" r="1.6" className="gh-earpiece" />
    </svg>
  );
}

export function GatehouseScene() {
  const stageRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [tilt, setTilt] = useState({ yaw: 0, pitch: 0 });
  const [paused, setPaused] = useState(false);
  const [offscreen, setOffscreen] = useState(false);

  // Mitoitus: maailma on kiinteän kokoinen, skaalataan säiliön leveyteen.
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      // Koko maailma (myös katto ja reittien päät) mahtuu sekä leveys- että korkeussuunnassa.
      const { width, height } = e.contentRect;
      setScale(Math.min(1.1, width / 660, height / 300));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Silmukka pysähtyy, kun näkymä ei ole näkyvissä tai välilehti on taustalla.
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

  const onMove = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const r = e.currentTarget.getBoundingClientRect();
    const dx = (e.clientX - r.left) / r.width - 0.5;
    const dy = (e.clientY - r.top) / r.height - 0.5;
    setTilt({ yaw: dx * 14, pitch: dy * -8 });
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

  const style = {
    "--gh-scale": scale,
    "--gh-yaw": `${-28 + tilt.yaw}deg`,
    "--gh-pitch": `${57 + tilt.pitch}deg`,
  } as CSSProperties;

  return (
    <div className={`gh${paused || offscreen ? " is-paused" : ""}`}>
      <div
        ref={stageRef}
        className="gh-stage"
        style={style}
        onPointerMove={onMove}
        onPointerLeave={() => setTilt({ yaw: 0, pitch: 0 })}
        role="img"
        aria-label="Illustration: a doorman in front of a glass gatehouse stops a red route at the door, while a green route walks through the doorway and out the other side."
      >
        <div className="gh-world" style={{ width: W, height: D }}>
          {/* Maa: varjot, sisälattia, reitit — kaikki samassa tasossa. */}
          <svg className="gh-ground" width={W} height={D} viewBox={`0 0 ${W} ${D}`} aria-hidden="true">
            <defs>
              <radialGradient id="gh-floor-glow" cx="50%" cy="52%" r="55%">
                <stop offset="0" stopColor="#c5ef5d" stopOpacity=".07" />
                <stop offset="1" stopColor="#c5ef5d" stopOpacity="0" />
              </radialGradient>
              <filter id="gh-soft" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="5" />
              </filter>
              <filter id="gh-softer" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2.4" />
              </filter>
            </defs>
            <ellipse cx={W / 2} cy={D / 2 + 10} rx={W * 0.5} ry={D * 0.46} fill="url(#gh-floor-glow)" />
            <polygon points={boxShadow} className="gh-shadow" filter="url(#gh-soft)" />
            <rect x={BOX.x} y={BOX.y} width={BOX.w} height={BOX.d} className="gh-floor" />
            {/* portsarin varjo: samaan suuntaan kuin kopin varjo */}
            <ellipse
              cx={FIGURE.x + (FIGURE.h * LIGHT.x) / 2}
              cy={FIGURE.y + (FIGURE.h * LIGHT.y) / 2}
              rx={figLen / 2 + 7}
              ry={7}
              transform={`rotate(${figAngle} ${FIGURE.x + (FIGURE.h * LIGHT.x) / 2} ${FIGURE.y + (FIGURE.h * LIGHT.y) / 2})`}
              className="gh-shadow gh-shadow-figure"
              filter="url(#gh-softer)"
            />
            <ellipse cx={FIGURE.x} cy={FIGURE.y} rx={12} ry={4.5} className="gh-contact" filter="url(#gh-softer)" />

            {/* reitit: himmeä pohja + liikkuva pulssi */}
            <path d={GREEN_ROUTE} className="gh-route gh-route-green" />
            <path d={RED_ROUTE} className="gh-route gh-route-red" />
            <path d={GREEN_ROUTE} pathLength={1} className="gh-pulse gh-pulse-green" />
            <path d={GREEN_ROUTE} pathLength={1} className="gh-pulse gh-pulse-green gh-pulse-late" />
            <path d={RED_ROUTE} pathLength={1} className="gh-pulse gh-pulse-red" />
            <circle cx={318} cy={324} r={9} className="gh-stop-ring" />
          </svg>

          {/* Koppi: seinät ja katto. Takaseinä ja vasen ensin, etuseinä viimeisenä. */}
          <Wall x={BOX.x + BOX.w} y={BOX.y} deg={180} width={BOX.w} height={BOX.h} className="gh-back">
            <DoorWall width={BOX.w} height={BOX.h} door={{ ...DOOR, x: BOX.w - (DOOR.x - BOX.x) - DOOR.w }} />
          </Wall>
          <Wall x={BOX.x} y={BOX.y} deg={90} width={BOX.d} height={BOX.h} className="gh-left">
            <PlainWall width={BOX.d} height={BOX.h} />
          </Wall>
          <Wall x={BOX.x + BOX.w} y={BOX.y + BOX.d} deg={-90} width={BOX.d} height={BOX.h} className="gh-right">
            <PlainWall width={BOX.d} height={BOX.h} />
          </Wall>
          <Wall x={BOX.x} y={BOX.y + BOX.d} deg={0} width={BOX.w} height={BOX.h} className="gh-front">
            <DoorWall width={BOX.w} height={BOX.h} door={{ ...DOOR, x: DOOR.x - BOX.x }} />
          </Wall>
          <div
            className="gh-roof"
            style={{
              width: BOX.w,
              height: BOX.d,
              transform: `translate3d(${BOX.x}px, ${BOX.y}px, ${BOX.h}px)`,
            }}
          />

          {/* Portsari oven edessä, käännetty kameraa kohti. */}
          <div
            className="gh-figure"
            style={{
              width: FIGURE.w,
              height: FIGURE.h,
              transformOrigin: `${FIGURE.w / 2}px ${FIGURE.h}px`,
              transform: `translate3d(${FIGURE.x - FIGURE.w / 2}px, ${FIGURE.y - FIGURE.h}px, 0) rotateZ(calc(-1 * var(--gh-yaw))) rotateX(-90deg)`,
            }}
          >
            <Bouncer />
          </div>
        </div>
      </div>
      <button
        type="button"
        className="gh-toggle"
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? "Play the gatehouse animation" : "Pause the gatehouse animation"}
        title={paused ? "Play" : "Pause"}
      >
        {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
      </button>
    </div>
  );
}
