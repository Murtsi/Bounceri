"""Viewed development counterexample: temporal spray membership is advisory only."""

from bouncer.contracts import Campaign, IpIntel
from bouncer.eval.run import network_signals
from bouncer.ingest.sample import parse_access_records
from bouncer.network import find_campaigns
from bouncer.session import rules, score
from tests.b.synthetic import human_session


def _record(at, ip, status, username=None, method="POST"):
    return {
        "ts": 1767225600.0 + at,
        "request": {
            "client_ip": ip,
            "remote_ip": ip,
            "method": method,
            "uri": "/login",
            "headers": {
                "User-Agent": [
                    "Mozilla/5.0 Chrome/131.0.0.0" if ip == "192.0.2.1" else "curl/8.5.0"
                ]
            },
        },
        "status": status,
        "size": 100,
        "resp_headers": {"X-Login-User": [username]} if username else {},
    }


def test_generic_spray_membership_never_promotes_session_to_bad_bot():
    campaign = Campaign(
        "spray:example", "distributed_login_spray", ("s1", "s2", "s3", "s4", "s5"), ()
    )
    assert rules.login_attack_rule(campaign) is None
    verdict = score(human_session(), IpIntel(), campaign, traps=frozenset(), model=None)
    assert verdict.label == "uncertain"
    assert verdict.model_version == "rules-v2"


def test_ordinary_retry_remains_uncertain_beside_advisory_spray_and_same_target_attack():
    ordinary = "192.0.2.1"
    records = [
        _record(0, ordinary, 200, method="GET"),
        _record(3, ordinary, 401, "ordinary-user"),
        _record(9, ordinary, 401, "ordinary-user"),
        _record(16, ordinary, 200, "ordinary-user"),
    ]
    for i in range(4):
        records.extend(
            _record(i * 0.1 + j * 4, f"198.51.100.{i + 1}", 401, "same-test-target")
            for j in range(3)
        )
    sessions, _ = parse_access_records(records, secret=None)
    campaigns = find_campaigns(sessions)
    assert any(c.kind == "distributed_login_spray" for c in campaigns)
    assert any(c.kind == "credential_stuffing" for c in campaigns)
    _, by_session = network_signals(sessions, None, find_campaigns)
    benign = next(s for s in sessions if s.ip == ordinary)
    assert by_session[benign.id].kind == "distributed_login_spray"
    assert (
        score(benign, IpIntel(), by_session[benign.id], traps=frozenset(), model=None).label
        == "uncertain"
    )
    attackers = [s for s in sessions if s.ip != ordinary]
    assert all(by_session[s.id].kind == "credential_stuffing" for s in attackers)
    assert all(
        score(s, IpIntel(), by_session[s.id], traps=frozenset(), model=None).label == "bad_bot"
        for s in attackers
    )


def test_native_viewed_development_retry_counterexample_stays_uncertain(tmp_path):
    from tools.datasets.native import evaluate_bundle, generate_bundle

    manifest = generate_bundle(tmp_path / "development", seed=7, runs_per_partition=1)
    report = evaluate_bundle(manifest)
    retry = [row for row in report["predictions"] if row["profile"] == "ordinary_login_retries"]
    assert len(retry) == 1 and retry[0]["prediction"] == "uncertain"
    assert {row["model_version"] for row in report["predictions"]} == {"rules-v2"}
    assert report["partitions"] == ["candidate_validation"]
