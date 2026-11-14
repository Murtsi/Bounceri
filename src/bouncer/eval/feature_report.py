"""Piirreraportti (B-3): miltä piirteet näyttävät luokittain oikeassa datassa.

Käyttö B-3:ssa heti kun A:n lokinäyte + `load_sessions()`/`load_labels()` ovat
olemassa:

    ds = build_dataset(load_sessions(since), load_labels())
    print(to_markdown(feature_report(ds)))
    for sid, obs in human_alarms(ds): ...   # käsin läpi → korjaukset / known_weaknesses

Raportti ei tee päätöksiä eikä tuota `metrics.json`-lukuja (ne tulevat B-7:stä).
Se kertoo, erottavatko piirteet luokat ja mitkä ihmissessiot laukaisevat
havaintoja — eli mistä väärät positiiviset tulisivat.
"""

from __future__ import annotations

import statistics
from collections.abc import Collection, Mapping, Sequence
from dataclasses import fields
from typing import Any

from bouncer.contracts import TRAFFIC_UNAVAILABLE_FEATURES
from bouncer.eval.dataset import Dataset, Origin
from bouncer.session import rules
from bouncer.session.features import SessionFeatures

FEATURE_NAMES = tuple(f.name for f in fields(SessionFeatures))


def _quantiles(values: list[float]) -> dict[str, float]:
    if len(values) == 1:
        v = values[0]
        return {"p10": v, "median": v, "p90": v}
    q = statistics.quantiles(values, n=10, method="inclusive")
    return {"p10": q[0], "median": statistics.median(values), "p90": q[-1]}


def summarise(
    feats: list[SessionFeatures],
    unavailable_features: Sequence[Collection[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Per piirre: lukumäärä, `None`-määrä ja p10/mediaani/p90 tai True-osuus."""
    out: dict[str, dict[str, Any]] = {}
    for name in FEATURE_NAMES:
        vals = [
            None if unavailable_features and name in unavailable_features[i] else getattr(x, name)
            for i, x in enumerate(feats)
        ]
        present = [v for v in vals if v is not None]
        entry: dict[str, Any] = {"n": len(vals), "missing": len(vals) - len(present)}
        if present and all(isinstance(v, bool) for v in present):
            entry["true_share"] = sum(present) / len(present)
        elif present:
            entry.update(_quantiles([float(v) for v in present]))
        out[name] = entry
    return out


def feature_report(
    ds: Dataset,
    *,
    unavailable_fields: Mapping[str, Collection[str]] | None = None,
    unlabeled_origin: Origin = "real",
) -> dict[str, Any]:
    """Jakaumat ryhmittäin `origin/truth` (simuloitu ja oikea erikseen) + labeloimattomat."""
    unavailable_fields = unavailable_fields or {}
    groups: dict[str, list[tuple[str, SessionFeatures]]] = {}
    for r in ds.rows:
        groups.setdefault(f"{r.origin}/{r.truth}", []).append((r.session_id, r.features))
    if ds.unlabeled:
        groups[f"{unlabeled_origin}/unlabeled"] = ds.unlabeled
    return {
        "summary": ds.summary(),
        "groups": {
            group: summarise(
                [features for _, features in rows],
                [
                    {name for field in unavailable_fields.get(sid, ())
                     for name in TRAFFIC_UNAVAILABLE_FEATURES.get(field, ())}
                    for sid, _ in rows
                ],
            )
            for group, rows in sorted(groups.items())
        },
    }


def human_alarms(ds: Dataset) -> list[tuple[str, list[str]]]:
    """Ihmisiksi labeloidut sessiot, joista löytyy bottihavaintoja.

    Nämä ovat väärien positiivisten ehdokkaita: käydään käsin läpi B-3:ssa ja
    B-9:ssä. Vähintään 2 haavoittuvuuspolkua = varma `bad_bot`-sääntö → aina mukana.
    """
    out = []
    for r in ds.rows:
        if r.truth != "human":
            continue
        obs = rules.observations(r.features)
        if r.features.vuln_path_hits >= rules.VULN_PATHS_CERTAIN:
            obs.insert(0, "VARMA SÄÄNTÖ: ≥ 2 haavoittuvuuspolkua")
        if obs:
            out.append((r.session_id, obs))
    return out


def _fmt(v: Any) -> str:
    return f"{v:.3g}" if isinstance(v, float) else str(v)


def to_markdown(report: dict[str, Any]) -> str:
    """Taulukko per ryhmä: piirre | n | puuttuu | p10 | mediaani | p90 | True-osuus."""
    lines = ["# Piirreraportti", "", "```", str(report["summary"]), "```", ""]
    for group, feats in report["groups"].items():
        lines += [f"## {group}", "", "| piirre | n | puuttuu | p10 | mediaani | p90 | True |"]
        lines.append("|---|---|---|---|---|---|---|")
        for name, e in feats.items():
            cells = [e.get(k, "") for k in ("n", "missing", "p10", "median", "p90", "true_share")]
            lines.append(f"| {name} | " + " | ".join(_fmt(c) for c in cells) + " |")
        lines.append("")
    return "\n".join(lines)
