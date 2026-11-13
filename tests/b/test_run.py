import json
from dataclasses import dataclass

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
