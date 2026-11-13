"""Labeloitu datasetti (B-5). Puhdas funktio: sessiot + labelit sisään, rivit ulos.

Oikeiden vastausten lähteet (ARCHITECTURE.md §5), etusijajärjestyksessä:

1. `sim`   — A:n simulaattorin `X-Sim-Run`-label (S10) → luokka + alaluokka
2. `dns`   — C:n DNS-varmistama hakukonebotti (`verified_bot is True`) → `good_bot`
3. `trap`  — ansaosuma (A:n `traps.txt`, S11) → `bad_bot`

Session ilman mitään näistä on *labeloimaton*: se ei mene opetukseen eikä
testiin, mutta lasketaan oikean liikenteen jakaumiin.

Ristiriidat (esim. simuloitu ihminen osui ansaan) EIVÄT muuta labelia — ne
listataan, koska ne ovat datan laatuvirheitä (ansa näkyvissä, simulaattorivirhe).
Päätökset 023–025.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from bouncer.session import rules
from bouncer.session._provisional_types import IpIntel, Label, Session, SessionLabel
from bouncer.session.features import SessionFeatures, compute_features

TruthSource = Literal["sim", "trap", "dns"]
Origin = Literal["simulated", "real"]

#: A:n simulaattoriluokat → B:n label. Tuntematon luokka ei koskaan arvaa
#: luokkaa, vaan päätyy `unmapped_classes`-listaan (päätös 023).
SIM_CLASS_TO_LABEL: dict[str, Label] = {
    "human": "human",
    "human_playwright": "human",
    "human_real": "human",
    "scraper": "bad_bot",
    "scanner": "bad_bot",
    "slow_scanner": "bad_bot",
    "credential_stuffing": "bad_bot",
    "brute_force": "bad_bot",
    "good_bot": "good_bot",
}


def sim_class_label(sim_class: str) -> Label | None:
    c = sim_class.strip().lower()
    if c in SIM_CLASS_TO_LABEL:
        return SIM_CLASS_TO_LABEL[c]
    if c.startswith("human"):
        return "human"
    return None


@dataclass(frozen=True, slots=True)
class DatasetRow:
    session_id: str
    started_at: datetime
    features: SessionFeatures
    truth: Label
    subclass: str  # simulaattorin luokka, "trap" tai "verified_crawler"
    source: TruthSource
    origin: Origin
    run_id: str | None = None
    campaign_id: str | None = None


@dataclass(frozen=True, slots=True)
class Conflict:
    session_id: str
    kept: str  # "sim:human"
    other: str  # "trap"


@dataclass(slots=True)
class Dataset:
    rows: list[DatasetRow] = field(default_factory=list)
    unlabeled: list[tuple[str, SessionFeatures]] = field(default_factory=list)
    unmapped_classes: dict[str, int] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    excluded_runs: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, object]:
        """Laskurit, joista näkee heti, onko datassa ongelmia."""
        by: dict[str, int] = {}
        for r in self.rows:
            key = f"{r.origin}/{r.source}/{r.truth}"
            by[key] = by.get(key, 0) + 1
        return {
            "labeled": len(self.rows),
            "unlabeled": len(self.unlabeled),
            "by_origin_source_truth": dict(sorted(by.items())),
            "unmapped_classes": dict(self.unmapped_classes),
            "conflicts": len(self.conflicts),
            "excluded_runs": dict(self.excluded_runs),
        }


def build_dataset(
    sessions: Iterable[Session],
    labels: Iterable[SessionLabel],
    intel_by_ip: Mapping[str, IpIntel] | None = None,
    traps: frozenset[str] = frozenset(),
    exclude_run_ids: Collection[str] = (),
) -> Dataset:
    """Kokoaa labeloidun datasetin.

    `exclude_run_ids`: ajot, joita ei saa käyttää (piilotettu hyökkäys ennen
    T+34, B-11). Niiden sessiot jätetään kokonaan pois, myös labeloimattomista.
    """
    intel_by_ip = intel_by_ip or {}
    excluded = set(exclude_run_ids)
    by_session: dict[str, SessionLabel] = {}
    for lab in labels:
        by_session[lab.session_id] = lab

    ds = Dataset()
    for s in sessions:
        lab = by_session.get(s.id)
        if lab is not None and lab.run_id in excluded:
            ds.excluded_runs[lab.run_id] = ds.excluded_runs.get(lab.run_id, 0) + 1
            continue

        feats = compute_features(s)
        trap_hit = rules.trap_rule(s, traps) is not None
        intel = intel_by_ip.get(s.ip)
        dns_ok = intel is not None and intel.verified_bot is True

        if lab is not None:
            truth = sim_class_label(lab.sim_class)
            if truth is None:
                ds.unmapped_classes[lab.sim_class] = ds.unmapped_classes.get(lab.sim_class, 0) + 1
                continue
            kept = f"sim:{truth}"
            if trap_hit and truth != "bad_bot":
                ds.conflicts.append(Conflict(s.id, kept, "trap"))
            if dns_ok and truth != "good_bot":
                ds.conflicts.append(Conflict(s.id, kept, "dns"))
            ds.rows.append(
                DatasetRow(
                    s.id,
                    s.started_at,
                    feats,
                    truth,
                    lab.sim_class.strip().lower(),
                    "sim",
                    "simulated",
                    lab.run_id,
                    lab.campaign_id,
                )  # fmt: skip
            )
        elif dns_ok:
            # DNS ennen ansaa samasta syystä kuin rules.evaluate (päätös 021).
            if trap_hit:
                ds.conflicts.append(Conflict(s.id, "dns:good_bot", "trap"))
            ds.rows.append(
                DatasetRow(s.id, s.started_at, feats, "good_bot", "verified_crawler", "dns", "real")
            )
        elif trap_hit:
            ds.rows.append(DatasetRow(s.id, s.started_at, feats, "bad_bot", "trap", "trap", "real"))
        else:
            ds.unlabeled.append((s.id, feats))
    return ds
