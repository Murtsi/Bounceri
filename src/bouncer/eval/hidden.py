"""Valittujen ajojen kehitysarviointi (B-11), ilman uudelleenopetusta.

Lataa tallennetun mallin ja raportoi valitut ajot ansoilla sekä ilman ansoja.
Mallin versio ja ajo-ID eivät todista jäädytystä tai riippumatonta hyökkäystä.
`--write` ei ole käytettävissä; tuotantojulkaisu edellyttää frozen native
evaluator -polun varmennettuja jäädytys-, sinetöinti- ja paljastuskuitteja.
"""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bouncer.contracts import Campaign, IpIntel, Session, SessionLabel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.evaluate import (
    LEGACY_PUBLICATION_ERROR,
    Thresholds,
    apply_thresholds,
    metrics_for,
)
from bouncer.eval.metrics import METRICS_PATH
from bouncer.session import model as mdl
from bouncer.session import rules
from bouncer.session.score import score


def evaluate_hidden(
    sessions: Sequence[Session],
    labels: Sequence[SessionLabel],
    run_ids: Sequence[str],
    model: mdl.LogisticModel,
    *,
    intel_by_ip: Mapping[str, IpIntel] | None = None,
    campaign_by_session: Mapping[Any, Campaign] | None = None,
    traps: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Kehitysluvut muuttamatta mallia; ei todiste riippumattomasta hyökkäyksestä."""
    if model.thresholds.get("bot") is None:
        raise ValueError("mallilla ei ole kalibroitua botti-kynnystä")
    wanted = set(run_ids)
    hidden_labels = [lab for lab in labels if lab.run_id in wanted]
    if not hidden_labels:
        raise ValueError(f"ei labeleita ajoille {sorted(wanted)}")
    intel_by_ip = intel_by_ip or {}
    campaign_by_session = campaign_by_session or {}
    traps = rules.load_traps() if traps is None else traps

    ds = build_dataset(sessions, hidden_labels, intel_by_ip, traps)
    rows = [r for r in ds.rows if r.source == "sim" and r.run_id in wanted]
    by_id = {s.id: s for s in sessions}
    th = Thresholds(model.thresholds.get("bot"), model.thresholds.get("human"), True)

    def preds(trap_set: frozenset[str]) -> dict[Any, Any]:
        sc = functools.partial(score, model=model, traps=trap_set)
        out = {}
        for r in rows:
            s = by_id[r.session_id]
            v = sc(s, intel_by_ip.get(s.ip), campaign_by_session.get(s.id))
            out[r.session_id] = apply_thresholds(v, th)
        return out

    with_traps = metrics_for(rows, preds(traps))
    without = metrics_for(rows, preds(frozenset()))
    return {
        **with_traps,
        "run_ids": sorted(wanted),
        "model_version": model.model_version,
        "retrained": False,
        "traps": "on",
        "without_traps": {
            "bot_recall": without["bot_recall"],
            "uncertain_share": without["uncertain_share"],
            "per_class": without["per_class"],
        },
        "unmapped_classes": dict(ds.unmapped_classes),
    }


def add_to_metrics(hidden: Mapping[str, Any], path: Path = METRICS_PATH) -> dict[str, Any]:
    """Deprecated publication entry point; a model version cannot prove independence."""
    raise ValueError(LEGACY_PUBLICATION_ERROR)


def main(argv: Sequence[str] | None = None) -> int:
    from bouncer.eval.run import load, network_signals

    ap = argparse.ArgumentParser(
        prog="python -m bouncer.eval.hidden", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--source", choices=("sample", "db"), default="db")
    ap.add_argument("--run", action="append", required=True, help="piilotetun hyökkäyksen ajo-ID")
    ap.add_argument("--offline", action="store_true", help="ei C:n DNS-hakuja eikä kampanjoita")
    ap.add_argument("--write", action="store_true", help="ei käytettävissä: käytä frozen evaluator")
    a = ap.parse_args(argv)
    if a.write:
        print(f"HUOM: {LEGACY_PUBLICATION_ERROR}")
        return 1

    model = mdl.load_model()
    if model is None:
        print("models/model.json puuttuu: tuotantomalli vaatii frozen native evaluator -julkaisun")
        return 1
    sessions, labels, _ = load(a.source)
    intel_fn = campaigns_fn = None
    if not a.offline:
        from bouncer.network import find_campaigns, ip_intel_contract

        # C:n virallinen B-polku: S4-muoto ilman C:n sisäistä threat_labelia (päätös 040)
        intel_fn, campaigns_fn = ip_intel_contract, find_campaigns
    intel, camps = network_signals(sessions, intel_fn, campaigns_fn)
    try:
        h = evaluate_hidden(
            sessions, labels, a.run, model, intel_by_ip=intel, campaign_by_session=camps
        )
    except ValueError as e:
        print(f"HUOM: {e}")
        return 1
    print(
        f"kehitysarviointi ajoille {h['run_ids']} ({h['model_version']}, ei uudelleenopetusta): "
        f"n={h['n']}, tunnistettu {h['bot_recall']}, epävarma {h['uncertain_share']}, "
        f"ilman ansoja {h['without_traps']['bot_recall']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
