"""Piilotettu hyökkäys (B-11): jäädytetty malli, ei uudelleenopetusta.

T+34 A paljastaa piilotetun hyökkäyksen ajo-ID:t. Silloin:

    PYTHONPATH=src python -m bouncer.eval.hidden --source db --run <ajo-id> [--run …] --write

1. Ladataan `models/model.json` sellaisenaan (malli + kynnykset). Mitään ei opeteta.
2. Ajetaan vain piilotetun hyökkäyksen sessiot `score()`:n läpi.
3. Pääluku tuotannon tavalla eli **ansat päällä**, ja vertailuksi muuhun
   arviointiin myös **ilman ansoja** (päätös 038).
4. `--write` lisää tuloksen `metrics.json`:n `split.hidden_attack`-kenttään
   sellaisenaan eikä muuta muita lukuja.

Ennen T+34 A:n `load_labels()` ei saa palauttaa piilotetun ajon labeleita;
silloin sessiot ovat B:lle labeloimattomia eivätkä päädy opetukseen.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bouncer.contracts import Campaign, IpIntel, Session, SessionLabel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.evaluate import Thresholds, apply_thresholds, metrics_for
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
    """Piilotetun hyökkäyksen luvut jäädytetyllä mallilla."""
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
    """Lisää tuloksen `split.hidden_attack`-kenttään. Muut luvut eivät muutu."""
    m = json.loads(path.read_text("utf-8"))
    if m.get("stub"):
        raise ValueError("metrics.json on stub: aja ensin oikea arviointi (B-7)")
    if m.get("data", {}).get("synthetic"):
        raise ValueError("metrics.json on laskettu synteettisellä datalla")
    if m.get("model_version") != hidden.get("model_version"):
        raise ValueError(
            f"mallin versio {hidden.get('model_version')} ≠ metrics.json "
            f"{m.get('model_version')}: piilotettu hyökkäys pitää ajaa samalla mallilla"
        )
    if m.get("split", {}).get("hidden_attack"):
        raise ValueError("split.hidden_attack on jo täytetty — tulosta ei ylikirjoiteta")
    m.setdefault("split", {})["hidden_attack"] = dict(hidden)
    path.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return m


def main(argv: Sequence[str] | None = None) -> int:
    from bouncer.eval.run import load, network_signals

    ap = argparse.ArgumentParser(
        prog="python -m bouncer.eval.hidden", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--source", choices=("sample", "db"), default="db")
    ap.add_argument("--run", action="append", required=True, help="piilotetun hyökkäyksen ajo-ID")
    ap.add_argument("--offline", action="store_true", help="ei C:n DNS-hakuja eikä kampanjoita")
    ap.add_argument("--write", action="store_true", help="lisää tulos metrics.json:iin")
    a = ap.parse_args(argv)

    model = mdl.load_model()
    if model is None:
        print("models/model.json puuttuu: opeta ja tallenna malli ensin (bouncer.eval.run --write)")
        return 1
    sessions, labels, synthetic = load(a.source)
    intel_fn = campaigns_fn = None
    if not a.offline:
        from bouncer.network import find_campaigns, ip_intel

        intel_fn, campaigns_fn = ip_intel, find_campaigns
    intel, camps = network_signals(sessions, intel_fn, campaigns_fn)
    try:
        h = evaluate_hidden(
            sessions, labels, a.run, model, intel_by_ip=intel, campaign_by_session=camps
        )
    except ValueError as e:
        print(f"HUOM: {e}")
        return 1
    print(
        f"piilotettu hyökkäys {h['run_ids']} ({h['model_version']}, ei uudelleenopetusta): "
        f"n={h['n']}, tunnistettu {h['bot_recall']}, epävarma {h['uncertain_share']}, "
        f"ilman ansoja {h['without_traps']['bot_recall']}"
    )
    if a.write:
        if synthetic:
            print("HUOM: --write ohitettu, data on synteettistä")
            return 1
        try:
            add_to_metrics(h)
        except ValueError as e:
            print(f"HUOM: {e}")
            return 1
        print("kirjoitettu: models/metrics.json (split.hidden_attack)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
