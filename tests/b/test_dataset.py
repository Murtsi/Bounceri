import dataclasses

import pytest

from bouncer.contracts import IpIntel, SessionLabel
from bouncer.eval.dataset import build_dataset, sim_class_label
from bouncer.eval.feature_report import feature_report, human_alarms, to_markdown

from .synthetic import (
    GOOGLEBOT_UA,
    curl_scanner_session,
    googlebot_session,
    human_session,
    req,
    scraper_session,
    session,
)

TRAPS = frozenset({"/hidden-link"})
GB_IP = "66.249.66.1"


def _sessions():
    return {
        "h1": session(list(human_session().requests), sid="h1"),
        "scan": session(list(curl_scanner_session().requests), ua="curl/8.5.0", sid="scan"),
        "scr": session(list(scraper_session().requests), sid="scr"),
        "gb": dataclasses.replace(
            session(list(googlebot_session().requests), ua=GOOGLEBOT_UA, sid="gb"), ip=GB_IP
        ),
        "trap": session([req(0, "/"), req(1, "/hidden-link")], sid="trap"),
        "anon": session([req(0, "/"), req(30, "/about")], sid="anon"),
    }


LABELS = [
    SessionLabel("h1", "run1", "human_playwright"),
    SessionLabel("scan", "run1", "scanner", "camp-1"),
    SessionLabel("scr", "run2", "scraper", "camp-2"),
]


@pytest.mark.parametrize(
    ("cls", "label"),
    [("human", "human"), ("Human_Playwright", "human"), ("human_qr", "human"),
     ("scraper", "bad_bot"), ("credential_stuffing", "bad_bot"), ("good_bot", "good_bot"),
     ("mystery", None)],
)  # fmt: skip
def test_sim_class_mapping(cls, label):
    assert sim_class_label(cls) == label


def test_build_dataset_sources_and_origins():
    s = _sessions()
    ds = build_dataset(
        s.values(), LABELS, intel_by_ip={GB_IP: IpIntel(verified_bot=True)}, traps=TRAPS
    )
    rows = {r.session_id: r for r in ds.rows}
    assert rows["h1"].source == "sim" and rows["h1"].truth == "human"
    assert rows["h1"].origin == "simulated"
    assert rows["scan"].truth == "bad_bot" and rows["scan"].campaign_id == "camp-1"
    assert rows["gb"].source == "dns" and rows["gb"].truth == "good_bot"
    assert rows["gb"].origin == "real"
    assert rows["trap"].source == "trap"  # eri IP → ei DNS-labelia
    assert [sid for sid, _ in ds.unlabeled] == ["anon"]


def test_trap_label_and_unlabeled():
    s = _sessions()
    ds = build_dataset([s["trap"], s["anon"]], [], traps=TRAPS)
    assert [(r.session_id, r.truth, r.source) for r in ds.rows] == [("trap", "bad_bot", "trap")]
    assert [sid for sid, _ in ds.unlabeled] == ["anon"]


def test_sim_label_wins_over_trap_and_conflict_is_reported():
    s = _sessions()
    lab = [SessionLabel("trap", "run3", "human")]
    ds = build_dataset([s["trap"]], lab, traps=TRAPS)
    assert ds.rows[0].truth == "human"
    assert [(c.session_id, c.kept, c.other) for c in ds.conflicts] == [
        ("trap", "sim:human", "trap")
    ]


def test_unmapped_class_is_not_guessed():
    s = _sessions()
    ds = build_dataset([s["h1"]], [SessionLabel("h1", "run1", "mystery")])
    assert ds.rows == [] and ds.unlabeled == []
    assert ds.unmapped_classes == {"mystery": 1}


def test_hidden_run_is_excluded_completely():
    s = _sessions()
    ds = build_dataset(s.values(), LABELS, exclude_run_ids={"run2"})
    ids = {r.session_id for r in ds.rows} | {sid for sid, _ in ds.unlabeled}
    assert "scr" not in ids
    assert ds.excluded_runs == {"run2": 1}


def test_summary_counts():
    s = _sessions()
    summ = build_dataset(s.values(), LABELS, traps=TRAPS).summary()
    assert summ["labeled"] == 4  # h1, scan, scr (sim) + trap
    assert summ["unlabeled"] == 2  # gb (ei intelia), anon
    assert summ["by_origin_source_truth"]["simulated/sim/bad_bot"] == 2


# --- piirreraportti (B-3) ------------------------------------------------------


def test_feature_report_groups_and_stats():
    s = _sessions()
    rep = feature_report(build_dataset(s.values(), LABELS, traps=TRAPS))
    assert set(rep["groups"]) == {
        "simulated/human", "simulated/bad_bot", "real/bad_bot", "real/unlabeled",
    }  # fmt: skip
    bots = rep["groups"]["simulated/bad_bot"]
    assert bots["static_share"]["median"] == 0.0
    assert bots["ua_is_tool"]["true_share"] == 0.5
    human = rep["groups"]["simulated/human"]
    assert human["interarrival_cv"]["missing"] == 0
    md = to_markdown(rep)
    assert "## simulated/human" in md and "| static_share |" in md


def test_feature_report_handles_all_missing_values():
    s = session([req(0, "/")], sid="one")
    rep = feature_report(build_dataset([s], [SessionLabel("one", "r", "human")]))
    cv = rep["groups"]["simulated/human"]["interarrival_cv"]
    assert cv == {"n": 1, "missing": 1}


def test_human_alarms_lists_suspicious_humans_only():
    s = _sessions()
    lab = [
        SessionLabel("h1", "r", "human"),
        SessionLabel("scr", "r", "human"),  # "ihminen", joka käyttäytyy kuin scraper
        SessionLabel("scan", "r", "scanner"),
    ]
    alarms = dict(human_alarms(build_dataset(s.values(), lab)))
    assert set(alarms) == {"scr"}
    assert any("CSS/JS" in o for o in alarms["scr"])


def test_human_alarm_flags_certain_rule():
    s = _sessions()
    alarms = dict(human_alarms(build_dataset([s["scan"]], [SessionLabel("scan", "r", "human")])))
    assert alarms["scan"][0].startswith("VARMA SÄÄNTÖ")
