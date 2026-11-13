import dataclasses
import json
from datetime import timedelta

import pytest

from bouncer.eval.dataset import build_dataset
from bouncer.eval.evaluate import (
    Thresholds,
    apply_thresholds,
    choose_thresholds,
    metrics_for,
    run_evaluation,
    wilson_upper,
    write_metrics,
)
from bouncer.eval.metrics import REQUIRED_KEYS
from bouncer.eval.split import temporal_split
from bouncer.session import MODEL_VERSION, score
from bouncer.session._provisional_types import IpIntel, Session, SessionLabel, Verdict

from .synthetic import (
    T0,
    curl_scanner_session,
    googlebot_session,
    human_session,
    req,
    scraper_session,
    session,
)

# --- synteettinen datasetti ----------------------------------------------------


def _shift(s: Session, sid: str, minutes: float, ip: str | None = None) -> Session:
    d = timedelta(minutes=minutes)
    reqs = tuple(dataclasses.replace(r, ts=r.ts + d, ip=ip or r.ip) for r in s.requests)
    return Session(sid, ip or s.ip, s.user_agent, s.started_at + d, s.ended_at + d, reqs)


def _corpus(n: int = 20):
    """n kpl jokaista arkkityyppiä, tasaisesti 10 h:n ajalle, jokaisella oma IP."""
    sessions, labels = {}, []
    makers = [
        ("human", human_session, "human_playwright"),
        ("scan", curl_scanner_session, "scanner"),
        ("scr", scraper_session, "scraper"),
    ]
    for i in range(n):
        for prefix, make, cls in makers:
            sid = f"{prefix}{i}"
            ip = f"10.{len(prefix)}.0.{i}"
            sessions[sid] = _shift(make(), sid, minutes=30 * i, ip=ip)
            labels.append(SessionLabel(sid, f"run-{prefix}-{i // 10}", cls))
    gb = _shift(googlebot_session(), "gb0", minutes=5, ip="66.249.66.1")
    sessions["gb0"] = gb
    intel = {"66.249.66.1": IpIntel(verified_bot=True)}
    return sessions, labels, intel


def _dataset():
    sessions, labels, intel = _corpus()
    return sessions, build_dataset(sessions.values(), labels, intel_by_ip=intel), intel


# --- jako ----------------------------------------------------------------------


def test_temporal_split_is_strictly_by_time():
    _, ds, _ = _dataset()
    sp = temporal_split(ds.rows, test_fraction=0.3)
    assert max(r.started_at for r in sp.train) < sp.cutoff <= min(r.started_at for r in sp.test)
    assert len(sp.train) + len(sp.test) == len(ds.rows)
    assert 0.25 < len(sp.test) / len(ds.rows) < 0.35


def test_temporal_split_reports_straddling_runs():
    _, ds, _ = _dataset()
    sp = temporal_split(ds.rows, cutoff=T0 + timedelta(minutes=30 * 15))
    assert "run-human-1" in sp.straddling_runs  # i = 10…19 → molemmin puolin


def test_temporal_split_rejects_empty_and_bad_fraction():
    with pytest.raises(ValueError):
        temporal_split([])
    _, ds, _ = _dataset()
    with pytest.raises(ValueError):
        temporal_split(ds.rows, test_fraction=1.0)


# --- kynnykset -----------------------------------------------------------------


def test_bot_threshold_respects_human_fpr():
    humans = [0.1] * 99 + [0.9]  # yksi ihminen 0.9:ssä = 1 %
    bots = [0.9] * 50 + [0.95] * 50
    th = choose_thresholds(humans, bots, max_human_fpr=0.01)
    assert th.bot == 0.9 and th.calibrated
    th_strict = choose_thresholds(humans, bots, max_human_fpr=0.0)
    assert th_strict.bot == 0.95


def test_human_threshold_below_bot_threshold():
    humans = [0.1, 0.2, 0.3] * 10
    bots = [0.2] + [0.8] * 99
    th = choose_thresholds(humans, bots)
    assert th.human is not None and th.bot is not None
    assert th.human < th.bot
    assert th.human == 0.3  # 1 % boteista ≤ 0.3 → sallittu (5 %)


def test_no_humans_means_not_calibrated():
    th = choose_thresholds([], [0.9, 1.0])
    assert th.bot is None and not th.calibrated


def test_rules_scores_never_predict_human():
    # rules-v1: ihmiset ja scraperit 0.5, varmat osumat 1.0 → kukaan ei ole "human"
    th = choose_thresholds([0.5] * 20, [0.5] * 20 + [1.0] * 20)
    assert th.bot == 1.0 and th.human is None


def test_apply_thresholds_keeps_good_bot():
    th = Thresholds(bot=0.8, human=0.2, calibrated=True)
    assert apply_thresholds(Verdict("good_bot", 1.0, ("x",), "v"), th) == "good_bot"
    assert apply_thresholds(Verdict("uncertain", 0.9, ("x",), "v"), th) == "bad_bot"
    assert apply_thresholds(Verdict("uncertain", 0.1, ("x",), "v"), th) == "human"
    assert apply_thresholds(Verdict("uncertain", 0.5, ("x",), "v"), th) == "uncertain"


# --- luvut ---------------------------------------------------------------------


def test_wilson_upper_bound():
    assert wilson_upper(0, 0) is None
    assert wilson_upper(0, 40) == pytest.approx(0.0876, abs=1e-3)  # 0/40 ei todista < 1 %
    assert wilson_upper(0, 400) < 0.01
    assert wilson_upper(5, 5) == 1.0


def test_metrics_for_counts_and_confusion():
    sessions, ds, _ = _dataset()
    rows = [r for r in ds.rows if r.session_id in {"human0", "human1", "scan0", "scr0"}]
    preds = {"human0": "human", "human1": "bad_bot", "scan0": "bad_bot", "scr0": "uncertain"}
    m = metrics_for(rows, preds)
    assert m["n"] == 4 and m["n_humans"] == 2
    assert m["human_fpr"] == 0.5
    assert m["bot_recall"] == 0.5
    assert m["uncertain_share"] == 0.25
    assert m["confusion"] == [[1, 0, 1, 0], [0, 0, 0, 0], [0, 0, 1, 1]]
    assert m["per_class"]["sub:scanner"] == {"n": 1, "recall": 1.0}
    assert m["per_class"]["sub:scraper"] == {"n": 1, "recall": 0.0}


# --- koko ajo rules-v1:llä -------------------------------------------------------


def test_run_evaluation_with_rules_v1():
    sessions, ds, intel = _dataset()
    res = run_evaluation(ds, sessions, score, MODEL_VERSION, synthetic=True, intel_by_ip=intel)
    m = res.metrics
    assert m.keys() >= REQUIRED_KEYS
    assert m["stub"] is False and m["data"]["synthetic"] is True
    assert m["data"]["excluded_dns_labelled"] == 1  # Googlebot: kehämäinen label
    assert m["threshold"] == {"bot": 1.0, "human": None}
    assert m["human_fpr"] == 0.0
    assert m["per_class"]["sub:scanner"]["recall"] == 1.0  # ≥ 2 haavoittuvuuspolkua
    assert m["per_class"]["sub:scraper"]["recall"] == 0.0  # säännöt eivät tunnista → malli
    assert m["split"]["real"]["n"] == 0
    assert m["split"]["simulated"]["n"] == m["data"]["n_test"]
    assert m["human_fpr_ci95_upper"] > 0.01  # liian vähän ihmisiä väitteeseen < 1 %
    json.dumps(m)


def test_traps_are_disabled_during_evaluation():
    # Ansaan osunut, muuten tavallinen sessio: label "trap" → ei saa tunnistua ansasta.
    sessions, ds, intel = _dataset()
    trap = _shift(
        session([req(0, "/"), req(20, "/hidden-link")]), "trap0", 30 * 19 + 10, ip="10.9.9.9"
    )
    sessions["trap0"] = trap
    ds2 = build_dataset(sessions.values(), [], traps=frozenset({"/hidden-link"}))
    labelled = {r.session_id for r in ds2.rows}
    assert "trap0" in labelled
    ds.rows.append(next(r for r in ds2.rows if r.session_id == "trap0"))
    res = run_evaluation(ds, sessions, score, MODEL_VERSION, synthetic=True, intel_by_ip=intel)
    real = res.metrics["split"]["real"]
    assert real["n"] == 1
    assert real["per_class"]["bad_bot"]["recall"] == 0.0


def test_ablation_without_network_signals():
    sessions, ds, _ = _dataset()
    # Väärennetty Googlebot testijaksolla: C:n verkostosignaali (verified_bot=False) tunnistaa sen.
    fake = _shift(googlebot_session(), "fake0", 30 * 19, ip="10.7.7.7")
    sessions["fake0"] = fake
    ds.rows.extend(build_dataset([fake], [SessionLabel("fake0", "run-f", "scraper")]).rows)
    intel = {"10.7.7.7": IpIntel(verified_bot=False)}
    res = run_evaluation(ds, sessions, score, MODEL_VERSION, synthetic=True, intel_by_ip=intel)
    with_net = res.metrics["per_class"]["bad_bot"]["recall"]
    without = res.metrics["ablation"]["without_network_signals"]["recall"]
    assert with_net > without


def test_hidden_attack_is_reported_separately():
    sessions, ds, intel = _dataset()
    hid = _shift(curl_scanner_session(), "hid0", 30 * 25, ip="10.8.8.8")
    sessions["hid0"] = hid
    hidden = build_dataset([hid], [SessionLabel("hid0", "hidden-run", "scanner")])
    res = run_evaluation(
        ds, sessions, score, MODEL_VERSION, synthetic=True, intel_by_ip=intel, hidden=hidden
    )
    assert res.metrics["split"]["hidden_attack"]["n"] == 1
    assert res.metrics["split"]["hidden_attack"]["bot_recall"] == 1.0
    assert "hid0" not in {r.session_id for r in res.split.train + res.split.test}


def test_write_metrics_refuses_synthetic(tmp_path):
    sessions, ds, intel = _dataset()
    res = run_evaluation(ds, sessions, score, MODEL_VERSION, synthetic=True, intel_by_ip=intel)
    with pytest.raises(ValueError, match="synteettisen"):
        write_metrics(res, tmp_path / "m.json")
    assert not (tmp_path / "m.json").exists()


def test_write_metrics_writes_real_result(tmp_path):
    sessions, ds, intel = _dataset()
    res = run_evaluation(ds, sessions, score, MODEL_VERSION, synthetic=False, intel_by_ip=intel)
    out = tmp_path / "m.json"
    write_metrics(res, out)
    assert json.loads(out.read_text("utf-8"))["stub"] is False
