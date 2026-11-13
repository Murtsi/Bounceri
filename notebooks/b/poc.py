"""Proof of concept: Caddy-loki → sessiot → C:n signaalit → B:n päätös → selitys.

    PYTHONPATH=src uv run --no-project --python 3.12 python notebooks/b/poc.py [--dns] [--md out.md]

Näyttää, että kaistojen puhtaat funktiot toimivat yhteen ilman tietokantaa:

    A  bouncer.ingest.sample.parse_access_records   Caddy JSONL → Session + SessionLabel
    C  bouncer.network.ip_intel_contract / find_campaigns
    B  bouncer.session.score                         säännöt (+ malli, jos annettu)
    C  bouncer.explain.explain(use_llm=False)        selitys ilman AI Routeria

EI ole A:n worker eikä tuotantoputki. Kaikki data on synteettistä:
- lokit: A:n näyte (`samples/`) + C:n tunnusten kokeilun fixture (`tests/c/fixtures/`)
- malli-sarake: `lr-v1` opetettu B:n synteettisillä testisessioilla, ei tallenneta.
  Sen luvut eivät ole mittaustulos.
`--dns` tekee oikeat DNS-haut (C:n Googlebot-varmistus); oletuksena ei verkkoa.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from bouncer.eval.dataset import build_dataset  # noqa: E402
from bouncer.eval.run import network_signals  # noqa: E402
from bouncer.eval.train import train_and_evaluate  # noqa: E402
from bouncer.explain import explain  # noqa: E402
from bouncer.ingest.sample import parse_access_records  # noqa: E402
from bouncer.network import find_campaigns, ip_intel_contract  # noqa: E402
from bouncer.session import rules, score  # noqa: E402

LOGS = (
    ROOT / "samples" / "access.sample.jsonl",
    ROOT / "tests" / "c" / "fixtures" / "stuffing_access.jsonl",
)


def read_logs(paths=LOGS):
    records = []
    for p in paths:
        records += [json.loads(line) for line in p.read_text("utf-8").splitlines() if line.strip()]
    records.sort(key=lambda r: r["ts"])
    return parse_access_records(records)


def synthetic_model():
    """lr-v1 B:n synteettisillä testisessioilla — vain demoa varten."""
    from tests.b.synthetic import corpus

    sessions, labels, intel = corpus()
    ds = build_dataset(sessions.values(), labels, intel_by_ip=intel)
    _, m = train_and_evaluate(ds, sessions, synthetic=True, intel_by_ip=intel)
    return m


def run(dns: bool = False) -> list[dict]:
    sessions, labels = read_logs()
    truth = {lab.session_id: lab.sim_class for lab in labels}
    intel_fn = ip_intel_contract if dns else None
    intel, camps = network_signals(sessions, intel_fn, find_campaigns)
    traps = rules.load_traps()
    model = synthetic_model()

    rows = []
    for s in sessions:
        i, c = intel.get(s.ip), camps.get(s.id)
        v_rules = score(s, i, c, traps=traps, model=None)
        v_model = score(s, i, c, traps=traps, model=model)
        rows.append({
            "id": str(s.id),
            "ip": s.ip,
            "ua": s.user_agent[:28],
            "requests": len(s.requests),
            "truth": truth.get(s.id, "—"),
            "rules": f"{v_rules.label} {v_rules.score:.2f}",
            "model": f"{v_model.label} {v_model.score:.2f}",
            "campaign": f"{c.kind}:{c.id}" if c else "—",
            "explain": explain(v_model, s, c, use_llm=False),
        })  # fmt: skip
    return rows


def to_markdown(rows: list[dict]) -> str:
    head = (
        "| # | IP | User-Agent | pyynt. | totuus | säännöt (rules-v1) "
        "| malli (lr-v1, synteettinen) | kampanja |"
    )
    out = ["# Bouncer PoC (synteettinen data)", "", head, "|" + "---|" * 8]
    for r in rows:
        out.append(
            f"| {r['id']} | {r['ip']} | `{r['ua']}` | {r['requests']} | {r['truth']} | "
            f"{r['rules']} | {r['model']} | {r['campaign']} |"
        )
    out += ["", "## Selitykset (C:n `explain`, ilman LLM:ää)", ""]
    out += [f"- **{r['id']}** ({r['model']}): {r['explain']}" for r in rows]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dns", action="store_true", help="tee oikeat DNS-haut (C)")
    ap.add_argument("--md", type=Path, default=None, help="kirjoita tulos Markdownina")
    a = ap.parse_args(argv)
    md = to_markdown(run(dns=a.dns))
    print(md)
    if a.md:
        a.md.write_text(md, "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
