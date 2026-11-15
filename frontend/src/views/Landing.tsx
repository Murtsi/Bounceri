import "./Landing.css";
import { ArrowRight, ChevronDown, Play, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "@/api";
import { BouncerLogo } from "@/components/BouncerLogo";
import { GatehouseScene, type GateMode } from "@/views/GatehouseScene";

/*
 * Etusivu (landing): kertoo ensikertalaiselle ja tuomarille, mikä Bounceri on,
 * miten se toimii ja mitä on oikeasti mitattu. Kaikki väitteet ja luvut tulevat
 * repon dokumenteista (IDEA.md, ARCHITECTURE.md, EVALUATION.md, HOSTINGER_LIVE.md);
 * yhtään lukua ei keksitä (AGENTS.md §7). Dashboard on yhden klikkauksen päässä.
 */

type Target = "overview" | "metrics" | "sessions";

const MEDIA = `${import.meta.env.BASE_URL}media/`;
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/**
 * Tunnelmatausta: demovideon pieni, äänetön versio sumennettuna heron takana.
 * Pysähtyy, kun hero ei ole näkyvissä; vähennetty liike → pelkkä pysäytyskuva.
 */
function HeroBackdrop() {
  const ref = useRef<HTMLVideoElement>(null);
  const [reduced] = useState(reducedMotion);
  useEffect(() => {
    const v = ref.current;
    if (!v || reduced) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) void v.play().catch(() => {});
      else v.pause();
    });
    io.observe(v);
    return () => io.disconnect();
  }, [reduced]);
  return (
    <div className="lp-hero-bg" aria-hidden="true">
      <video
        ref={ref}
        src={reduced ? undefined : `${MEDIA}bouncer-demo-bg.mp4`}
        poster={`${MEDIA}bouncer-demo-poster.jpg`}
        muted
        loop
        playsInline
        autoPlay={!reduced}
        preload={reduced ? "none" : "auto"}
        tabIndex={-1}
      />
    </div>
  );
}

/** Demovideo modaalissa: natiivi <dialog> (fokus, Esc), ääni ja säätimet päällä. */
function DemoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      void video.current?.play().catch(() => {});
    } else if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={dialog}
      className="lp-dialog"
      aria-label="Bounceri demo video"
      onClose={() => {
        video.current?.pause();
        onClose();
      }}
      onClick={(e) => {
        // Klikkaus taustalle (dialogin ulkopuolelle) sulkee.
        if (e.target === dialog.current) dialog.current?.close();
      }}
    >
      <div className="lp-dialog-frame">
        <video
          ref={video}
          src={`${MEDIA}bouncer-demo.mp4`}
          poster={`${MEDIA}bouncer-demo-poster.jpg`}
          controls
          playsInline
          preload="metadata"
        />
        <button type="button" className="lp-dialog-close" onClick={() => dialog.current?.close()} aria-label="Close video">
          <X aria-hidden="true" />
        </button>
      </div>
    </dialog>
  );
}

const STEPS = [
  {
    title: "Collect",
    text: "Your site’s traffic passes through Caddy. Every request becomes a structured log line; nothing is sampled away.",
  },
  {
    title: "Group",
    text: "Requests are stitched into sessions by address, browser and timing, then described with features a person can read: pace, regularity, assets fetched, paths, headers.",
  },
  {
    title: "Decide",
    text: "Certain rules go first: trap links, vulnerability probes, fake Googlebots that fail DNS verification. When the evidence is thin, Bouncer answers “uncertain” instead of guessing.",
  },
  {
    title: "Connect",
    text: "Sessions that share a target, a tool and a time window are linked into one campaign, so six addresses guessing passwords for the same account read as one attacker.",
  },
];

const DIFFERENT = [
  {
    title: "Every verdict shows its reasons",
    text: "Up to three plain-language reasons per session. A language model may narrate a finished verdict; it never makes the call, and the reasons stay when it is offline.",
  },
  {
    title: "The error rate is public",
    text: "Measured results and known weaknesses are published next to the product, including the parts we cannot detect yet.",
  },
  {
    title: "It recommends, it never blocks",
    text: "Monitor, rate-limit, challenge or block: Bouncer suggests the step that fits the evidence. The site owner stays in control.",
  },
];

const MODULES = [
  { name: "Clean the traffic", note: "Live today", live: true },
  { name: "Spot the swarm", note: "Social coordination · later", live: false },
  { name: "Name the technique", note: "Text manipulation · later", live: false },
  { name: "Trust the source", note: "Source provenance · later", live: false },
];

export default function Landing({ open }: { open: (t: Target) => void }) {
  const [mode, setMode] = useState<GateMode>("idle");
  const [demoOpen, setDemoOpen] = useState(false);
  // Merkintä "synthetic" vain, kun API kertoo datan olevan synteettistä (ei kovakoodattuna).
  const { data: summary } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const synthetic = summary?.synthetic === true;
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="lp">
      <header className="lp-bar">
        <button
          type="button"
          className="lp-brand home-link"
          aria-label="Bounceri home"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          <BouncerLogo mode="static" className="text-[22px]" />
        </button>
        <nav aria-label="Page sections" className="lp-links">
          <button type="button" onClick={() => jump("how")}>How it works</button>
          <button type="button" onClick={() => jump("proof")}>Results</button>
          <button type="button" onClick={() => jump("hostinger")}>On Hostinger</button>
        </nav>
        <button type="button" className="lp-cta lp-cta-sm" onClick={() => open("overview")}>
          Open dashboard <ArrowRight aria-hidden="true" />
        </button>
      </header>

      <main>
        {/* Hero: lupaus vasemmalla, elävä porttikoppi oikealla. */}
        <section className="lp-hero" aria-labelledby="lp-title">
          <HeroBackdrop />
          <div className="lp-hero-copy">
            {/* Otsikon "Bouncer" on sama logo kuin latausruudussa: B:n alakaari ponnauttaa "ouncer"-sanan. */}
            <h1 id="lp-title">
              Every session meets <span className="lp-h1-brand">the{" "}<BouncerLogo mode="play" className="lp-h1-logo" />.</span>
            </h1>
            <p className="lp-lede">
              Bounceri reads your website’s traffic session by session and tells you who is really at the door: a
              person, a good bot or an attacker. It shows why, and how often it is wrong.
            </p>
            <div className="lp-actions">
              <button type="button" className="lp-cta" onClick={() => open("overview")}>
                Open the live dashboard <ArrowRight aria-hidden="true" />
              </button>
              <button type="button" className="lp-ghost" onClick={() => setDemoOpen(true)}>
                <Play aria-hidden="true" /> Watch the 20-second demo
              </button>
              <button type="button" className="lp-ghost lp-ghost-quiet" onClick={() => jump("how")}>
                How it works <ChevronDown aria-hidden="true" />
              </button>
            </div>
            <p className={`lp-live is-${mode}`} role="status">
              <i aria-hidden="true" />
              {mode === "live"
                ? "Live: the dots are sessions arriving right now"
                : mode === "replay"
                  ? "Each dot is a real recent session, replayed while traffic is quiet"
                  : "Waiting for traffic"}
              {synthetic && <span> · synthetic traffic</span>}
            </p>
          </div>
          <div className="lp-hero-scene">
            <GatehouseScene onMode={setMode} />
            <ul className="lp-key" aria-label="What the dots mean">
              <li><i className="sw sw-pass" aria-hidden="true" />Walks through · human or good bot</li>
              <li><i className="sw sw-stop" aria-hidden="true" />Held at the door · bad bot</li>
              <li><i className="sw sw-check" aria-hidden="true" />Checked first · uncertain</li>
            </ul>
          </div>
        </section>

        {/* Ongelma */}
        <section className="lp-section lp-problem" aria-labelledby="lp-problem">
          <h2 id="lp-problem">Your visitor count is padded with bots.</h2>
          <div className="lp-prose">
            <p>
              Scanners, scrapers and scripts trying stolen passwords find a public site within hours. The owner of a
              small site or web shop sees a pile of log lines, or a visitor number that quietly includes all of them.
            </p>
            <p>
              Off-the-shelf bot blockers are black boxes. They block too much or too little, real customers get
              locked out, and none of them tells you how often it is wrong.
            </p>
          </div>
        </section>

        {/* Miten toimii: järjestys kantaa tietoa, siksi numeroidut vaiheet. */}
        <section id="how" className="lp-section" aria-labelledby="lp-how">
          <h2 id="lp-how">From log line to verdict in four steps.</h2>
          <ol className="lp-steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="lp-step-n" aria-hidden="true">{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Erottautuminen */}
        <section className="lp-section" aria-labelledby="lp-diff">
          <h2 id="lp-diff">Not another black box.</h2>
          <ul className="lp-diff">
            {DIFFERENT.map((d) => (
              <li key={d.title}>
                <h3>{d.title}</h3>
                <p>{d.text}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* Rehellinen näyttö: luvut EVALUATION.md:n varatusta ajosta, ehtoineen. */}
        <section id="proof" className="lp-section lp-proof" aria-labelledby="lp-proof">
          <h2 id="lp-proof">Measured, and honest about it.</h2>
          <div className="lp-proof-grid">
            <p className="lp-proof-lead">
              On a frozen synthetic run that was evaluated once, <strong>10 of 10</strong> bad-bot calls were correct,{" "}
              <strong>0 of 14</strong> simulated humans were flagged, and <strong>18 of 28</strong> sessions were left
              uncertain instead of guessed.
            </p>
            <div className="lp-proof-caveat">
              <p>
                That traffic was written by our own team, so the numbers prove the pipeline works, not that it works
                on your visitors. Zero false alarms in 14 still allows a rate of up to 21.5% (95% upper bound). We do
                not claim the 1% target until about 300 labelled real human sessions back it.
              </p>
              <button type="button" className="lp-link" onClick={() => open("metrics")}>
                See metrics and known weaknesses <ArrowRight aria-hidden="true" />
              </button>
            </div>
          </div>
        </section>

        {/* Hostinger */}
        <section id="hostinger" className="lp-section lp-host" aria-labelledby="lp-host">
          <h2 id="lp-host">Runs end to end on Hostinger.</h2>
          <div className="lp-prose">
            <p>
              Caddy, the ingest worker, the detector, PostgreSQL, the API and this dashboard run in Docker Compose on a
              Hostinger KVM 2 VPS at <strong>bounceri.tech</strong>. Detection works locally without any API key.
              Optional advisory reviews use Featherless models behind a shared spending budget, and are stored apart
              from the evidence.
            </p>
          </div>
          <ul className="lp-modules" aria-label="Investigation modules">
            {MODULES.map((m) => (
              <li key={m.name} className={m.live ? "is-live" : undefined}>
                <strong>{m.name}</strong>
                <span>{m.note}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* Loppukehotus */}
        <section className="lp-final" aria-labelledby="lp-final">
          <h2 id="lp-final">See who’s at the door right now.</h2>
          <button type="button" className="lp-cta" onClick={() => open("overview")}>
            Open the live dashboard <ArrowRight aria-hidden="true" />
          </button>
        </section>
      </main>

      <DemoDialog open={demoOpen} onClose={() => setDemoOpen(false)} />

      <footer className="lp-foot">
        <span>Built in 48 hours at Junction 2026 by Murtsi, Niko and Joonas for Hostinger’s Decode the Noise.</span>
        <span>Advisory: Bouncer recommends actions and never blocks requests itself.</span>
      </footer>
    </div>
  );
}
