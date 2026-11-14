from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from dataclasses import fields

from bouncer.contracts import Campaign, IpIntel, Request, Session, SessionLabel, Verdict
from bouncer.ingest.simrun import IngestStats
from bouncer.ingest.sample import (
    load_sample_labels,
    load_sample_sessions,
    parse_access_record,
    parse_access_records,
    parse_sim_run,
)
from bouncer.session._provisional_types import (
    Campaign as SessionCampaign,
    IpIntel as SessionIpIntel,
    Request as SessionRequest,
    Session as SessionSession,
    SessionLabel as SessionSessionLabel,
    Verdict as SessionVerdict,
)

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "access.sample.jsonl"


def _records() -> list[dict[str, object]]:
    return [json.loads(line) for line in SAMPLE.read_text(encoding="utf-8").splitlines()]


def test_shared_contract_types_match_b_provisional_field_names() -> None:
    for canonical, provisional in (
        (Request, SessionRequest),
        (Session, SessionSession),
        (IpIntel, SessionIpIntel),
        (Campaign, SessionCampaign),
        (SessionLabel, SessionSessionLabel),
        (Verdict, SessionVerdict),
    ):
        assert [field.name for field in fields(canonical)] == [
            field.name for field in fields(provisional)
        ]
    assert Campaign("c1", "test", ("1",)).session_ids == ("1",)


def test_fixture_is_valid_caddy_jsonl_and_sessionizes_to_expected_types() -> None:
    sessions = load_sample_sessions()
    labels = load_sample_labels()

    assert len(sessions) == 3
    assert sorted(len(session.requests) for session in sessions) == [1, 2, 3]
    assert all(isinstance(session, Session) for session in sessions)
    assert all(isinstance(request, Request) for session in sessions for request in session.requests)
    browser_session = next(session for session in sessions if session.ip == "198.51.100.10")
    assert browser_session.requests[0].path == "/"
    assert browser_session.requests[0].headers["user-agent"] == browser_session.user_agent
    assert browser_session.requests[0].content_type == "text/html"
    assert [label.sim_class for label in labels] == ["scanner"]
    assert labels[0].run_id == "scan-20261114-001"
    assert labels[0].campaign_id == "campaign-scan-01"
    assert labels[0].session_id == next(
        session.id for session in sessions if session.ip == "203.0.113.24"
    )


def test_sample_loader_does_not_treat_header_as_forwarded_client_ip() -> None:
    records = _records()
    records[0]["request"]["headers"]["X-Forwarded-For"] = ["203.0.113.222"]  # type: ignore[index]
    records[0]["request"]["remote_ip"] = "198.51.100.10"  # type: ignore[index]

    request, _ = parse_access_record(records[0])

    assert request.ip == "198.51.100.10"


def test_sim_run_parser_handles_missing_campaign_and_rejects_malformed_marker() -> None:
    assert parse_sim_run("run-1:human_playwright", 7) == SessionLabel(
        "7", "run-1", "human_playwright", None
    )
    with pytest.raises(ValueError, match="Invalid X-Sim-Run"):
        parse_sim_run("run-only", "7")


def test_conflicting_simulator_truth_gets_no_label_and_is_counted() -> None:
    records = _records()[:2]
    records[0]["request"]["headers"]["X-Sim-Run"] = ["run-a:scanner:campaign-a"]  # type: ignore[index]
    records[1]["request"]["headers"]["X-Sim-Run"] = ["run-b:scraper:campaign-b"]  # type: ignore[index]

    stats = IngestStats()
    sessions, labels = parse_access_records(records, secret=None, stats=stats)
    assert sessions and labels == []  # ei arvattua totuutta, mutta lukeminen jatkuu
    assert stats.conflicting_sessions == [sessions[0].id]


def test_sessionization_splits_after_five_minutes() -> None:
    records = _records()[:3]
    later = json.loads(json.dumps(records[0]))
    later["ts"] = "2026-11-14T12:06:00Z"
    records.append(later)

    sessions, _ = parse_access_records(records, idle_timeout=timedelta(minutes=5))

    assert len(sessions) == 2


def test_loaders_reject_malformed_jsonl(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_sample_sessions(bad)
