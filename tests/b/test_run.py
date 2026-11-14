import json
from dataclasses import dataclass

import pytest

from bouncer.contracts import IpIntel
from bouncer.eval import run as runner
from bouncer.session import model as mdl

from .synthetic import corpus

# --- A:n näyte -----------------------------------------------------------------


def test_sample_offline_reports_too_little_data():
    sessions, labels, synthetic = runner.load("sample")
    r = runner.run(sessions, labels, synthetic=synthetic)
    assert r.synthetic is True
    assert r.metrics is None and "liian vähän labeloitua dataa" in r.error
    assert "# Piirreraportti" in r.report_md


def test_cli_sample_exit_codes(tmp_path, capsys):
    assert runner.main(["--source", "sample", "--offline"]) == 0
    assert "SYNTEETTINEN" in capsys.readouterr().out
    # --write synteettisellä datalla → virhekoodi, eikä mitään tallenneta models/:iin
    assert runner.main(["--source", "sample", "--offline", "--write"]) == 1
    assert mdl.load_model() is None
    rep = tmp_path / "r.md"
    assert runner.main(["--source", "sample", "--offline", "--report", str(rep)]) == 0
    assert rep.read_text("utf-8").startswith("# Piirreraportti")


def test_db_source_reads_a_store_and_its_synthetic_flag(tmp_path, monkeypatch):
    from bouncer.db import seed_from_sample

    store = tmp_path / "store.json"
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(store))
    sessions, labels, synthetic = runner.load("db")
    assert (sessions, labels, synthetic) == ([], [], False)  # tyhjä store
    seed_from_sample(path=store)
    sessions, labels, synthetic = runner.load("db")
    assert len(sessions) == 3 and len(labels) == 1
    assert synthetic is True  # näytteestä seedattu → ei saa kirjoittaa oikeiksi luvuiksi
    assert all(isinstance(s.id, str) for s in sessions)


# --- C:n signaalit ---------------------------------------------------------------


@dataclass
class FakeCampaign:
    id: str
    kind: str
    session_ids: list


def test_network_signals_map_int_campaign_ids_and_dedupe_ips():
    sessions, _, _ = corpus(n=3)
    calls = []

    def intel_fn(ip):
        calls.append(ip)
        return IpIntel(asn_type="datacenter")

    ids = list(sessions)
    camp = FakeCampaign("k1", "stuffing", [ids[0], 999])  # str-ID + tuntematon
    intel, by_sess = runner.network_signals(list(sessions.values()), intel_fn, lambda s: [camp])
    assert len(calls) == len(set(calls)) == len({s.ip for s in sessions.values()})
    assert by_sess == {ids[0]: camp}
    assert all(i.asn_type == "datacenter" for i in intel.values())


# --- koko ajo --------------------------------------------------------------------


def test_run_on_synthetic_corpus_refuses_write():
    sessions, labels, intel = corpus()
    r = runner.run(
        list(sessions.values()), labels, synthetic=True,
        intel_fn=lambda ip: intel.get(ip, IpIntel()), write=True,
    )  # fmt: skip
    assert r.metrics is not None and r.metrics["model_version"] == "lr-v1"
    assert r.saved is False and "synteettistä" in r.error
    lines = runner.summary_lines(r)
    assert any(line.startswith("ihmisten FPR") for line in lines)


def test_run_on_real_data_writes_metrics_and_model(tmp_path):
    sessions, labels, intel = corpus()
    mp, mo = tmp_path / "metrics.json", tmp_path / "model.json"
    r = runner.run(
        list(sessions.values()), labels, synthetic=False,
        intel_fn=lambda ip: intel.get(ip, IpIntel()), write=True,
        metrics_path=mp, model_path=mo,
    )  # fmt: skip
    assert r.saved and r.error is None
    assert json.loads(mp.read_text("utf-8"))["stub"] is False
    assert mdl.load_model(mo).thresholds["bot"] is not None


def test_exclude_runs_drops_hidden_attack():
    sessions, labels, _ = corpus()
    r = runner.run(list(sessions.values()), labels, synthetic=True, exclude_runs=["run-scr-1"])
    assert r.dataset["excluded_runs"] == {"run-scr-1": 10}


def test_import_context_never_invents_site_trap_or_current_dns_truth(monkeypatch):
    from dataclasses import replace
    sessions, _, _ = runner.load("sample")
    session = sessions[0]
    external = replace(session, requests=(replace(session.requests[0], path="/ordinary-page"),))
    monkeypatch.setattr(runner.rules, "load_traps", lambda: frozenset({"/ordinary-page"}))
    def forbidden_dns(ip):
        raise AssertionError("historical import cannot get current DNS truth")
    result = runner.run([external], [], synthetic=False, intel_fn=forbidden_dns,
                        allow_site_labels=False)
    assert result.dataset["labeled"] == 0
    assert result.dataset["unlabeled"] == 1


def test_synthetic_unlabeled_report_keeps_simulated_origin():
    sessions, _, _ = runner.load("sample")
    result = runner.run(sessions[:1], [], synthetic=True, allow_site_labels=False)
    assert "## simulated/unlabeled" in result.report_md
    assert "## real/unlabeled" not in result.report_md


def test_incomplete_labeled_data_refuses_training_and_writes(tmp_path, monkeypatch):
    sessions, labels, _ = corpus()
    session_id = labels[0].session_id

    def forbidden_training(*args, **kwargs):
        raise AssertionError("incomplete feature contracts must not reach training")

    monkeypatch.setattr(runner, "train_and_evaluate", forbidden_training)
    result = runner.run(
        list(sessions.values()), labels, synthetic=False, allow_site_labels=False,
        unavailable_fields={session_id: ["bytes"]}, write=True,
        metrics_path=tmp_path / "metrics.json", model_path=tmp_path / "model.json",
    )
    assert result.error == (
        "opetus/arviointi estetty: labeloiduista sessioista puuttuu piirteiden lähdetietoja"
    )
    assert result.metrics is None and not result.saved and not result.written
    assert list(tmp_path.iterdir()) == []


def test_cli_import_masks_report_and_never_loads_site_traps_or_dns(tmp_path, monkeypatch):
    from bouncer import network
    from bouncer.db.store import _serialize_session, _write_raw

    sessions, _, _ = runner.load("sample")
    imported = sessions[0]
    store = tmp_path / "import.json"
    _write_raw({
        "sessions": [_serialize_session(imported)], "labels": [], "synthetic": False,
        "trap_policy": "unavailable_for_import",
        "unavailable_fields": {imported.id: ["headers", "user_agent", "content_type"]},
    }, store)
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(store))
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("historical import must not load current site or DNS truth")

    monkeypatch.setattr(runner.rules, "load_traps", forbidden)
    monkeypatch.setattr(network, "ip_intel_contract", forbidden)
    report = tmp_path / "report.md"
    assert runner.main(["--source", "db", "--report", str(report)]) == 0
    text = report.read_text("utf-8")
    assert "## real/unlabeled" in text
    assert "| header_inconsistency_share | 1 | 1 |  |  |  |  |" in text
    assert "| ua_is_tool | 1 | 1 |  |  |  |  |" in text


def test_db_source_without_provenance_reader_fails_closed(monkeypatch):
    from bouncer.db import store

    monkeypatch.delattr(store, "is_synthetic")
    with pytest.raises(SystemExit, match="provenance is unknown"):
        runner.load("db")
