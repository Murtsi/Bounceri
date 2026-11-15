import json

import pytest

from bouncer.contracts import SessionLabel
from bouncer.eval import hidden as hid
from bouncer.eval.dataset import build_dataset
from bouncer.eval.train import train_and_evaluate

from .synthetic import corpus, curl_scanner_session, human_session, req, session, shift

TRAPS = frozenset({"/hidden-link"})


@pytest.fixture(scope="module")
def frozen():
    """Malli opetettu tavallisella aineistolla; piilotettu hyökkäys ei ole mukana."""
    sessions, labels, intel = corpus()
    ds = build_dataset(sessions.values(), labels, intel_by_ip=intel)
    res, m = train_and_evaluate(ds, sessions, synthetic=True, intel_by_ip=intel)
    return res, m


def _hidden():
    """Kaksi piilotetun ajon sessiota: ihmistä matkiva ansaan osuva + skanneri."""
    mimic = list(human_session().requests) + [req(110, "/hidden-link")]
    s1 = shift(session(mimic), "hid-mimic", 900, ip="10.66.0.1")
    s2 = shift(curl_scanner_session(), "hid-scan", 905, ip="10.66.0.2")
    labels = [SessionLabel("hid-mimic", "hidden-1", "scraper"),
              SessionLabel("hid-scan", "hidden-1", "scanner")]  # fmt: skip
    return [s1, s2], labels


def test_hidden_uses_frozen_model_and_reports_traps_separately(frozen):
    _, m = frozen
    before = (list(m.weights), m.bias, dict(m.thresholds))
    sessions, labels = _hidden()
    h = hid.evaluate_hidden(sessions, labels, ["hidden-1"], m, traps=TRAPS)
    assert (list(m.weights), m.bias, dict(m.thresholds)) == before  # ei opetettu
    assert h["n"] == 2 and h["retrained"] is False and h["run_ids"] == ["hidden-1"]
    assert h["model_version"] == "lr-v1" and h["traps"] == "on"
    assert h["bot_recall"] == 1.0  # ansat päällä: ihmistä matkiva jää ansaan
    assert h["without_traps"]["bot_recall"] == 0.5  # ilman ansoja malli pitää sitä ihmisenä


def test_hidden_ignores_other_runs(frozen):
    _, m = frozen
    sessions, labels = _hidden()
    other = shift(curl_scanner_session(), "other", 910, ip="10.66.0.3")
    h = hid.evaluate_hidden(
        [*sessions, other], [*labels, SessionLabel("other", "run-x", "scanner")],
        ["hidden-1"], m, traps=TRAPS,
    )  # fmt: skip
    assert h["n"] == 2


def test_hidden_requires_labels_and_thresholds(frozen):
    _, m = frozen
    sessions, labels = _hidden()
    with pytest.raises(ValueError, match="ei labeleita"):
        hid.evaluate_hidden(sessions, labels, ["nope"], m, traps=TRAPS)
    import dataclasses

    raw = dataclasses.replace(m, thresholds={"bot": None, "human": None})
    with pytest.raises(ValueError, match="kynnys"):
        hid.evaluate_hidden(sessions, labels, ["hidden-1"], raw, traps=TRAPS)


# --- metrics.json ------------------------------------------------------------------


def _real_metrics(frozen, tmp_path):
    res, _ = frozen
    m = json.loads(json.dumps(res.metrics))
    m["data"]["synthetic"] = False  # A misleading flag is not release evidence.
    p = tmp_path / "metrics.json"
    p.write_text(json.dumps(m), "utf-8")
    return p, m


def test_add_to_metrics_refuses_version_match_without_frozen_receipts(frozen, tmp_path):
    _, model = frozen
    p, _ = _real_metrics(frozen, tmp_path)
    before = p.read_bytes()
    sessions, labels = _hidden()
    h = hid.evaluate_hidden(sessions, labels, ["hidden-1"], model, traps=TRAPS)
    with pytest.raises(ValueError, match="frozen native evaluator"):
        hid.add_to_metrics(h, p)
    assert p.read_bytes() == before


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(stub=True),
        lambda m: m["data"].update(synthetic=True),
        lambda m: m.update(model_version="rules-v1"),
    ],
)
def test_add_to_metrics_refuses(frozen, tmp_path, change):
    _, model = frozen
    p, m = _real_metrics(frozen, tmp_path)
    change(m)
    p.write_text(json.dumps(m), "utf-8")
    before = p.read_bytes()
    sessions, labels = _hidden()
    h = hid.evaluate_hidden(sessions, labels, ["hidden-1"], model, traps=TRAPS)
    with pytest.raises(ValueError, match="frozen native evaluator"):
        hid.add_to_metrics(h, p)
    assert p.read_bytes() == before


def test_add_to_metrics_refuses_before_creating_missing_file(tmp_path):
    p = tmp_path / "metrics.json"
    with pytest.raises(ValueError, match="frozen native evaluator"):
        hid.add_to_metrics({"model_version": "rules-v1"}, p)
    assert not p.exists()


def test_cli_write_refuses_before_loading_model_or_traffic(monkeypatch, capsys):
    from bouncer.eval import run as runner

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy write must fail before loading model or traffic")

    monkeypatch.setattr(hid.mdl, "load_model", forbidden)
    monkeypatch.setattr(runner, "load", forbidden)
    assert hid.main(["--source", "db", "--run", "hidden-1", "--write"]) == 1
    assert "frozen native evaluator" in capsys.readouterr().out


def test_cli_without_saved_model(monkeypatch, capsys):
    monkeypatch.setattr(hid.mdl, "load_model", lambda: None)
    assert hid.main(["--source", "sample", "--offline", "--run", "x"]) == 1
    assert "model.json puuttuu" in capsys.readouterr().out
