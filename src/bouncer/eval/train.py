"""Mallin opetus + arviointi yhdellä kutsulla (B-6 + B-7).

    result, model = train_and_evaluate(dataset, sessions, synthetic=False, intel_by_ip=…)
    write_metrics(result)                 # models/metrics.json
    save_model(model, synthetic=False)    # models/model.json → score() käyttää sitä

Tuotantomalli on täsmälleen se malli, jonka luvut `metrics.json` kertoo (opetettu
vain opetusosalla, kynnykset kalibrointiosalta). Sitä ei opeteta uudelleen koko
datalla, koska silloin luvut eivät enää kuvaisi tuotannossa olevaa mallia.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from typing import Any

from bouncer.contracts import Campaign, IpIntel, Session
from bouncer.eval.dataset import Dataset, DatasetRow
from bouncer.eval.evaluate import EvalResult, Fit, Scorer, run_evaluation
from bouncer.session import model as mdl
from bouncer.session.score import score


def make_fit(
    sessions: Mapping[str, Session],
    intel_by_ip: Mapping[str, IpIntel],
    campaign_by_session: Mapping[str, Campaign],
) -> Fit:
    def _fit(rows: Sequence[DatasetRow], network: bool) -> tuple[Scorer, Any]:
        xs, ys = [], []
        for r in rows:
            s = sessions[r.session_id]
            intel = intel_by_ip.get(s.ip) if network else None
            camp = campaign_by_session.get(s.id) if network else None
            xs.append(mdl.vectorize(r.features, intel, camp, network))
            ys.append(0 if r.truth == "human" else 1)
        m = mdl.fit(xs, ys, network=network)
        return functools.partial(score, model=m), m

    return _fit


def train_and_evaluate(
    dataset: Dataset,
    sessions: Mapping[str, Session],
    *,
    synthetic: bool,
    intel_by_ip: Mapping[str, IpIntel] | None = None,
    campaign_by_session: Mapping[str, Campaign] | None = None,
    hidden: Dataset | None = None,
    known_weaknesses: Sequence[str] | None = None,
) -> tuple[EvalResult, mdl.LogisticModel]:
    intel_by_ip = intel_by_ip or {}
    campaign_by_session = campaign_by_session or {}
    res = run_evaluation(
        dataset,
        sessions,
        score,
        mdl.MODEL_VERSION,
        synthetic=synthetic,
        intel_by_ip=intel_by_ip,
        campaign_by_session=campaign_by_session,
        hidden=hidden,
        known_weaknesses=known_weaknesses,
        fit=make_fit(sessions, intel_by_ip, campaign_by_session),
    )
    m: mdl.LogisticModel = res.model
    m.thresholds = {"bot": res.thresholds.bot, "human": res.thresholds.human}
    m.trained = {
        "synthetic": synthetic,
        "cutoff": res.metrics["data"]["cutoff"],
        "n_fit": res.metrics["data"]["n_fit"],
        "n_calib": res.metrics["data"]["n_calib"],
        "thresholds_calibrated": res.thresholds.calibrated,
    }
    return res, m
