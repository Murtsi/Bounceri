"""Kirjaa stuffing-fixturen kampanjaluvut erilliseen tiedostoon (synteettinen).

Ei koske tuotannon `campaign_metrics.json`-stubia (AGENTS §7).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bouncer.ingest.sample import load_sample_data
from bouncer.network.campaigns import find_campaigns
from bouncer.network.eval import evaluate_campaigns

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "c" / "fixtures" / "stuffing_access.jsonl"
OUT = Path(__file__).with_name("campaign_metrics.fixture.json")


def measure_fixture(path: Path = FIXTURE) -> dict:
    sessions, labels = load_sample_data(path)
    camps = find_campaigns(sessions, include_behavior=False)
    truth = [(lab.session_id, lab.campaign_id) for lab in labels]
    metrics = evaluate_campaigns(camps, truth)
    metrics["synthetic"] = True
    metrics["source"] = str(path.as_posix())
    metrics["note"] = (
        "Synthetic C-4 fixture only — not production S9. "
        "Do not copy into dashboard as live campaign_metrics."
    )
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help=f"kirjoita {OUT.name}")
    args = ap.parse_args()
    metrics = measure_fixture()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    if args.write:
        OUT.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
