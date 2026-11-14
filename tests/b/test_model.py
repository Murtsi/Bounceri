import json

import pytest

from bouncer.contracts import Campaign, IpIntel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.evaluate import write_metrics
from bouncer.eval.train import train_and_evaluate
from bouncer.session import model as mdl
from bouncer.session import score
from bouncer.session.features import compute_features

from .synthetic import corpus, curl_scanner_session, human_session, scraper_session

# --- lineaarialgebra ja opetus -------------------------------------------------


def test_solve():
    assert mdl._solve([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0]) == pytest.approx([0.8, 1.4])
    with pytest.raises(ValueError):
        mdl._solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_fit_learns_direction_and_is_deterministic():
    xs = [[float(i)] for i in range(20)]
    ys = [1 if i >= 10 else 0 for i in range(20)]
    m1 = mdl.fit(xs, ys, network=True)
    m2 = mdl.fit(xs, ys, network=True)
    assert m1.weights == m2.weights and m1.bias == m2.bias
    assert m1.predict_proba([19.0]) > 0.9 > 0.1 > m1.predict_proba([0.0])


def test_fit_requires_both_classes():
    with pytest.raises(ValueError):
        mdl.fit([[1.0], [2.0]], [1, 1])


def test_vectorize_network_flag_drops_c_signals():
    f = compute_features(human_session())
    intel = IpIntel(asn_type="datacenter")
    camp = Campaign("c1", "stuffing", ("s1",))
    full = mdl.vectorize(f, intel, camp, network=True)
    nonet = mdl.vectorize(f, intel, camp, network=False)
    assert len(full) == len(mdl.feature_names(True)) == len(nonet) + 3
    assert dict(zip(mdl.feature_names(True), full, strict=True))["asn_datacenter"] == 1.0
    assert dict(zip(mdl.feature_names(True), full, strict=True))["in_campaign"] == 1.0


def test_model_roundtrip_and_feature_mismatch(tmp_path):
    xs = [mdl.vectorize(compute_features(s()), None, None) for s in
          (human_session, scraper_session, human_session, curl_scanner_session)]  # fmt: skip
    m = mdl.fit(xs, [0, 1, 0, 1])
    d = m.to_dict()
    m2 = mdl.LogisticModel.from_dict(json.loads(json.dumps(d)))
    assert m2.predict_proba(xs[1]) == pytest.approx(m.predict_proba(xs[1]))
    d["names"] = d["names"][:-1]
    with pytest.raises(ValueError, match="opeta uudelleen"):
        mdl.LogisticModel.from_dict(d)


# --- koko putki synteettisellä datalla ---------------------------------------------


@pytest.fixture(scope="module")
def trained():
    sessions, labels, intel = corpus()
    ds = build_dataset(sessions.values(), labels, intel_by_ip=intel)
    res, m = train_and_evaluate(ds, sessions, synthetic=True, intel_by_ip=intel)
    return sessions, res, m


def test_train_and_evaluate_uses_fit_calib_test(trained):
    _, res, m = trained
    d = res.metrics["data"]
    assert d["n_fit"] + d["n_calib"] == d["n_train"]
    assert d["n_fit"] > 0 and d["n_calib"] > 0
    assert res.metrics["model_version"] == "lr-v1"
    assert m.thresholds["bot"] is not None
    assert m.trained["synthetic"] is True


def test_model_detects_scrapers_that_rules_miss(trained):
    _, res, _ = trained
    pc = res.metrics["per_class"]
    assert pc["sub:scraper"]["recall"] == 1.0  # rules-v1: 0.0
    assert pc["sub:scanner"]["recall"] == 1.0
    assert res.metrics["human_fpr"] == 0.0
    assert pc["human"]["recall"] == 1.0  # malli voi päättää "human"


def test_ablation_is_retrained_without_network(trained):
    _, res, _ = trained
    ab = res.metrics["ablation"]["without_network_signals"]
    assert ab["recall"] is not None and ab["human_fpr"] is not None


def test_score_with_model_gives_three_reasons(trained):
    sessions, _, m = trained
    v = score(sessions["scr19"], None, None, traps=frozenset(), model=m)
    assert v.label == "bad_bot" and v.model_version == "lr-v1"
    assert len(v.reasons) == 3
    assert all("raised bot probability" in r for r in v.reasons)
    h = score(sessions["human19"], None, None, traps=frozenset(), model=m)
    assert h.label == "human"
    assert all("lowered bot probability" in r for r in h.reasons)


def test_reasons_skip_unmeasurable_features(trained):
    from .synthetic import CURL_UA, req, session

    _, _, m = trained
    one = session([req(0, "/login", ua=CURL_UA, status=401, content_type="text/plain")], ua=CURL_UA)
    v = score(one, None, None, traps=frozenset(), model=m)
    joined = " ".join(v.reasons)
    for word in (
        "Average rate",
        "Peak rate",
        "Session lasted",
        "interval variation",
        "Referer",
        "browser headers",
    ):
        assert word not in joined, (word, v.reasons)


def test_rules_still_win_over_model(trained):
    sessions, _, m = trained
    v = score(sessions["scan19"], None, None, traps=frozenset(), model=m)
    assert v.label == "bad_bot" and v.score == 1.0
    assert v.reasons[0].startswith("Probed")


def test_synthetic_model_and_metrics_are_never_saved(trained, tmp_path):
    _, res, m = trained
    with pytest.raises(ValueError, match="synteettisellä"):
        mdl.save_model(m, tmp_path / "model.json", synthetic=True)
    with pytest.raises(ValueError, match="synteettisen"):
        write_metrics(res, tmp_path / "metrics.json")
    assert not any(tmp_path.iterdir())


def test_saved_model_is_loaded_by_score(trained, tmp_path):
    sessions, _, m = trained
    p = tmp_path / "model.json"
    mdl.save_model(m, p, synthetic=False)  # testiä varten: polku tmp, ei models/
    loaded = mdl.load_model(p)
    assert loaded is not None
    v = score(sessions["scr19"], None, None, traps=frozenset(), model=loaded)
    assert v.label == "bad_bot"


def test_no_model_file_in_repo_means_rules_only():
    assert mdl.load_model() is None  # models/model.json ei ole commitoitu
    assert score(scraper_session(), None, None).model_version == "rules-v1"
