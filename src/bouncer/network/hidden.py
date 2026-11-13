"""C-10: piilotettu hyökkäys kampanjana — tulos sellaisenaan, ei uudelleensäätöä.

T+34 A paljastaa ajo-ID:t. Silloin (kun sessiot + labelit saatavilla):

    PYTHONPATH=src python -m bouncer.network.hidden \\
        --source sample|db --run <ajo-id> [--run …]

1. Suodatetaan vain paljastetun ajon sessiot.
2. Ajetaan `find_campaigns()` sellaisenaan (ei kynnysten säätöä).
3. Mitataan purity/coverage A:n `campaign_id`-labeleita vasten.
4. Raportoidaan löytyikö kampanja — myös jos ei löytynyt.

`--write` päivittää `campaign_metrics.json`:n `hidden_attack`-kentän
muuttamatta purity/coverage-stubia, jos ne ovat vielä stub.
Synteettisellä datalla `--write` kieltäytyy (rehellisyys).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bouncer.contracts import Session, SessionLabel
from bouncer.network.campaigns import find_campaigns
from bouncer.network.eval import METRICS_PATH, evaluate_campaigns, write_metrics
from bouncer.network.pipeline import campaign_to_api, campaigns_by_session
from bouncer.network.session_view import as_session_view


def _load(
    source: str,
) -> tuple[list[Session], list[SessionLabel], bool]:
    if source == "sample":
        from bouncer.ingest.sample import load_sample_data

        sessions, labels = load_sample_data()
        return sessions, labels, True
    if source == "db":
        try:
            from bouncer.db import load_labels, load_sessions  # type: ignore[attr-defined]
        except ImportError as exc:
            raise SystemExit(
                "bouncer.db.load_sessions/load_labels (A, S3) puuttuu — käytä --source sample"
            ) from exc
        return list(load_sessions(None)), list(load_labels()), False
    raise SystemExit(f"tuntematon lähde: {source}")


def evaluate_hidden_campaigns(
    sessions: Sequence[Session],
    labels: Sequence[SessionLabel],
    run_ids: Sequence[str],
) -> dict[str, Any]:
    """Löytyykö piilotettu ajo kampanjana? Ei säätöä — tulos sellaisenaan."""
    wanted = set(run_ids)
    hidden_labels = [lab for lab in labels if lab.run_id in wanted]
    if not hidden_labels:
        raise ValueError(f"ei labeleita ajoille {sorted(wanted)}")

    hidden_sids = {str(lab.session_id) for lab in hidden_labels}
    hidden_sessions = [s for s in sessions if str(as_session_view(s).id) in hidden_sids]
    if not hidden_sessions:
        raise ValueError(f"ei sessioita ajoille {sorted(wanted)}")

    predicted = find_campaigns(hidden_sessions)
    truth = [(lab.session_id, lab.campaign_id) for lab in hidden_labels]
    metrics = evaluate_campaigns(predicted, truth)
    by_session = campaigns_by_session(predicted)

    return {
        "run_ids": sorted(wanted),
        "n_sessions": len(hidden_sessions),
        "n_labels": len(hidden_labels),
        "found_campaign": bool(predicted),
        "n_predicted": len(predicted),
        "campaigns": [campaign_to_api(c) for c in predicted],
        "sessions_in_any_campaign": sorted(by_session),
        "purity": metrics["purity"],
        "coverage": metrics["coverage"],
        "retrained": False,
        "stub": False,
        "known_weaknesses": metrics["known_weaknesses"],
    }


def add_hidden_to_metrics(
    hidden: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    """Kirjoita `hidden_attack` campaign_metrics.json:iin; muut kentät säilyvät."""
    target = path or METRICS_PATH
    current = json.loads(target.read_text(encoding="utf-8"))
    if current.get("hidden_attack"):
        raise ValueError("hidden_attack on jo täytetty — älä ylikirjoita")
    current["hidden_attack"] = {
        "run_ids": hidden["run_ids"],
        "found_campaign": hidden["found_campaign"],
        "n_predicted": hidden["n_predicted"],
        "purity": hidden["purity"],
        "coverage": hidden["coverage"],
        "retrained": False,
    }
    write_metrics(current, target)
    return current


def summary_lines(result: dict[str, Any]) -> list[str]:
    lines = [
        f"hidden runs: {result['run_ids']}",
        f"sessions/labels: {result['n_sessions']}/{result['n_labels']}",
        f"found_campaign: {result['found_campaign']} (n={result['n_predicted']})",
        f"purity: {result['purity']}",
        f"coverage: {result['coverage']}",
        "retrained: False",
    ]
    for camp in result.get("campaigns") or []:
        lines.append(f"  - {camp['id']} ({camp['kind']}, size={camp['size']})")
    if not result.get("found_campaign"):
        lines.append("HUOM: piilotettu ajo ei klusteroitunut kampanjaksi — raportoi sellaisenaan")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m bouncer.network.hidden",
        description=__doc__.split("\n")[0],
    )
    ap.add_argument("--source", choices=("sample", "db"), default="sample")
    ap.add_argument("--run", action="append", default=[], required=True, dest="runs")
    ap.add_argument(
        "--write",
        action="store_true",
        help="kirjoita hidden_attack campaign_metrics.json:iin (ei synteettisellä)",
    )
    args = ap.parse_args(argv)

    sessions, labels, synthetic = _load(args.source)
    try:
        result = evaluate_hidden_campaigns(sessions, labels, args.runs)
    except ValueError as exc:
        print(f"HUOM: {exc}", file=sys.stderr)
        return 1

    print("\n".join(summary_lines(result)))
    if args.write:
        if synthetic:
            print("HUOM: --write ohitettu: data on synteettistä", file=sys.stderr)
            return 1
        add_hidden_to_metrics(result)
        print(f"kirjoitettu: {METRICS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
