"""Kehitysraportti ja ajallinen arviointi: `python -m bouncer.eval.run`.

    # A:n näyte (synteettinen), ilman DNS-hakuja:
    PYTHONPATH=src python -m bouncer.eval.run --source sample --offline

    # Yksityinen kehitysraportti:
    PYTHONPATH=src python -m bouncer.eval.run --source db --report notebooks/b/report.md

Vaiheet: lataa sessiot + labelit → C:n `ip_intel()` + `find_campaigns()` →
datasetti → piirreraportti + ihmishälytykset → mallin opetus ja kehitysarviointi.

`--write` ei ole käytettävissä: tämä polku ei varmista riippumatonta holdoutia.
Tuotantojulkaisu edellyttää frozen native evaluator -polun varmennettuja kuitteja
ja julkaisunäyttöä. `--exclude-run` ei yksin todista riippumatonta hyökkäystä.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from bouncer.contracts import IpIntel, Session, SessionLabel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.evaluate import LEGACY_PUBLICATION_ERROR
from bouncer.eval.feature_report import feature_report, human_alarms, to_markdown
from bouncer.eval.train import train_and_evaluate
from bouncer.session import rules

#: Vähimmäismäärä kumpaakin luokkaa, jotta opetus/kalibrointi/testi -jako on mahdollinen.
MIN_PER_CLASS = 10

#: Kun sessio kuuluu moneen C:n kampanjaan, B käyttää tarkinta (pienempi = ensin).
CAMPAIGN_PRIORITY = {"credential_stuffing": 0}

IntelFn = Callable[[str], Any]
CampaignsFn = Callable[[Sequence[Session]], Iterable[Any]]


@dataclass(slots=True)
class RunResult:
    synthetic: bool
    dataset: dict[str, Any]
    n_human_alarms: int
    metrics: dict[str, Any] | None = None
    error: str | None = None
    written: list[str] = field(default_factory=list)
    saved: bool = False  # metrics.json + model.json kirjoitettu
    report_md: str = ""


def load(
    source: str, since: datetime | None = None
) -> tuple[list[Session], list[SessionLabel], bool]:
    """Palauttaa (sessiot, labelit, synteettinen?)."""
    if source == "sample":
        from bouncer.ingest.sample import load_sample_data

        sessions, labels = load_sample_data()
        return sessions, labels, True  # A: näyte on synteettinen
    if source == "db":
        try:
            from bouncer.db import load_labels, load_sessions  # type: ignore[attr-defined]
        except ImportError as e:
            raise SystemExit(
                "bouncer.db.load_sessions/load_labels (A, S3) puuttuu vielä — käytä --source sample"
            ) from e
        # A:n store kertoo, onko sisältö synteettistä (esim. `bouncer.db seed` näytteestä).
        # Tuntematon alkuperä ei saa päätyä oikeiksi arviointiluvuiksi.
        try:
            from bouncer.db.store import is_synthetic
        except ImportError as e:
            raise SystemExit(
                "traffic source provenance is unknown; is_synthetic is unavailable"
            ) from e
        else:
            synthetic = is_synthetic()
        return list(load_sessions(since)), list(load_labels()), synthetic
    raise SystemExit(f"tuntematon lähde: {source}")


def network_signals(
    sessions: Sequence[Session],
    intel_fn: IntelFn | None,
    campaigns_fn: CampaignsFn | None,
) -> tuple[dict[str, IpIntel], dict[Any, Any]]:
    """C:n signaalit B:n muotoon. Kampanjat yhdistetään sessioon ID:n merkkijonona,
    koska C:n `Campaign.session_ids` voi olla int (S2-linjaus kesken)."""
    intel_by_ip = {ip: intel_fn(ip) for ip in sorted({s.ip for s in sessions})} if intel_fn else {}
    by_str = {str(s.id): s.id for s in sessions}
    camps = list(campaigns_fn(sessions)) if campaigns_fn else []
    # Sama sessio voi kuulua moneen kampanjaan; tarkin tyyppi voittaa (päätös 042).
    camps.sort(key=lambda c: CAMPAIGN_PRIORITY.get(getattr(c, "kind", ""), len(CAMPAIGN_PRIORITY)))
    campaign_by_session: dict[Any, Any] = {}
    for camp in camps:
        for sid in camp.session_ids:
            if str(sid) in by_str:
                campaign_by_session.setdefault(by_str[str(sid)], camp)
    return intel_by_ip, campaign_by_session


def run(
    sessions: Sequence[Session],
    labels: Sequence[SessionLabel],
    *,
    synthetic: bool,
    intel_fn: IntelFn | None = None,
    campaigns_fn: CampaignsFn | None = None,
    exclude_runs: Sequence[str] = (),
    write: bool = False,
    metrics_path: Path | None = None,
    model_path: Path | None = None,
    allow_site_labels: bool = True,
    unavailable_fields: Mapping[str, Collection[str]] | None = None,
) -> RunResult:
    if write:
        return RunResult(synthetic, {}, 0, error=LEGACY_PUBLICATION_ERROR)
    intel_by_ip, campaign_by_session = network_signals(
        sessions, intel_fn if allow_site_labels else None, campaigns_fn
    )
    ds = build_dataset(
        sessions, labels, intel_by_ip, rules.load_traps() if allow_site_labels else frozenset(),
        exclude_runs,
    )
    out = RunResult(synthetic, ds.summary(), len(human_alarms(ds)))
    out.report_md = to_markdown(feature_report(
        ds, unavailable_fields=unavailable_fields,
        unlabeled_origin="simulated" if synthetic else "real",
    ))

    if unavailable_fields and any(unavailable_fields.get(r.session_id) for r in ds.rows):
        out.error = (
            "opetus/arviointi estetty: labeloiduista sessioista puuttuu piirteiden lähdetietoja"
        )
        return out

    n_h = sum(r.truth == "human" for r in ds.rows if r.source != "dns")
    n_b = sum(r.truth != "human" for r in ds.rows if r.source != "dns")
    if n_h < MIN_PER_CLASS or n_b < MIN_PER_CLASS:
        out.error = (
            f"liian vähän labeloitua dataa opetukseen: ihmisiä {n_h}, botteja {n_b} "
            f"(tarvitaan ≥ {MIN_PER_CLASS} kumpaakin; "
            "ihmisten FPR < 1 % vaatii ~300 ihmistä testiin)"
        )
        return out

    try:
        res, _ = train_and_evaluate(
            ds,
            {s.id: s for s in sessions},
            synthetic=synthetic,
            intel_by_ip=intel_by_ip,
            campaign_by_session=campaign_by_session,
        )
    except ValueError as e:
        out.error = f"opetus/arviointi ei onnistunut: {e}"
        return out
    out.metrics = res.metrics

    return out


def _fmt(v: Any) -> str:
    return "—" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)


def summary_lines(r: RunResult) -> list[str]:
    lines = [
        f"data: {'SYNTEETTINEN' if r.synthetic else 'oikea'}",
        f"datasetti: {r.dataset}",
        f"ihmishälytyksiä (käsin läpi): {r.n_human_alarms}",
    ]
    if r.metrics:
        m, d = r.metrics, r.metrics["data"]
        lines += [
            f"malli: {m['model_version']}  kynnykset: {m['threshold']}",
            f"opetus/kalibrointi/testi: {d['n_fit']}/{d['n_calib']}/{d['n_test']}",
            f"ihmisten FPR: {_fmt(m['human_fpr'])} "
            f"(95 % yläraja {_fmt(m['human_fpr_ci95_upper'])}, n={m['per_class']['human']['n']})",
            f"epävarmojen osuus: {_fmt(m['uncertain_share'])}",
            f"ablaatio ilman C:tä: {m['ablation']['without_network_signals']}",
        ]
    if r.error:
        lines.append(f"HUOM: {r.error}")
    lines += [f"kirjoitettu: {p}" for p in r.written]
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m bouncer.eval.run", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--source", choices=("sample", "db"), default="sample")
    ap.add_argument("--since", type=datetime.fromisoformat, default=None, help="db: alkaen (ISO)")
    ap.add_argument("--offline", action="store_true", help="ei C:n DNS-hakuja eikä kampanjoita")
    ap.add_argument("--exclude-run", action="append", default=[], help="piilotettu ajo (B-11)")
    ap.add_argument("--write", action="store_true", help="ei käytettävissä: käytä frozen evaluator")
    ap.add_argument("--report", type=Path, default=None, help="piirreraportti Markdownina")
    a = ap.parse_args(argv)
    if a.write:
        print(f"HUOM: {LEGACY_PUBLICATION_ERROR}")
        return 1

    sessions, labels, synthetic = load(a.source, a.since)
    intel_fn = campaigns_fn = None
    if not a.offline:
        from bouncer.network import find_campaigns, ip_intel_contract

        # C:n virallinen B-polku: S4-muoto ilman C:n sisäistä threat_labelia (päätös 040)
        intel_fn, campaigns_fn = ip_intel_contract, find_campaigns
    allow_site_labels = True
    unavailable_fields = None
    if a.source == "db":
        from bouncer.db.store import read_snapshot

        snapshot = read_snapshot()
        allow_site_labels = snapshot.get("trap_policy") != "unavailable_for_import"
        unavailable_fields = snapshot.get("unavailable_fields")
    r = run(
        sessions, labels, synthetic=synthetic, intel_fn=intel_fn, campaigns_fn=campaigns_fn,
        exclude_runs=a.exclude_run, write=a.write, allow_site_labels=allow_site_labels,
        unavailable_fields=unavailable_fields,
    )  # fmt: skip
    if a.report:
        a.report.write_text(r.report_md + "\n", "utf-8")
        r.written.append(str(a.report))
    print("\n".join(summary_lines(r)))
    return 1 if a.write and not r.saved else 0


if __name__ == "__main__":
    sys.exit(main())
