"""Private replay evidence binds the actual native score inputs, never labels."""

import importlib
import json
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update

from bouncer.contracts import IpIntel, Request, Session
from bouncer.db.store import _session_from_dict
from bouncer.db.traffic import sources
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_participants import enroll, review, source, study  # noqa: F401, F811

NOW = datetime(2026, 11, 14, 0, 1, tzinfo=UTC).isoformat()
UNKNOWN_INTEL = IpIntel()


def api():
    assert importlib.util.find_spec("bouncer.ingest.runtime_context"), "runtime capture missing"
    return importlib.import_module("bouncer.ingest.runtime_context")


def session():
    ts = datetime(2026, 11, 14, tzinfo=UTC)
    request = Request(ts, "192.0.2.1", "GET", "/", 200, "fixture")
    return Session("same-session", request.ip, request.user_agent, ts, ts, (request,))


def observation(intel=UNKNOWN_INTEL, outcome="unavailable"):
    return dict(checked_at=NOW, resolver_outcome=outcome, **asdict(intel),
                crawler="googlebot" if intel.verified_bot is True else None,
                asn_origin="curated-prefix" if intel.asn else "unknown")


def captured(s=None, intel=UNKNOWN_INTEL, obs=None, enabled=True):
    s = s or session()
    configuration = api().capture_configuration(frozenset({"/private-trap", "/x"}))
    context = api().capture_session(s, intel, configuration=configuration, captured_at=NOW,
                                    intel_enabled=enabled, observation=obs)
    return s, configuration, context


@pytest.mark.parametrize("intel,outcome", [
    (IpIntel(), "timeout"), (IpIntel(verified_bot=False), "mismatch"),
    (IpIntel(verified_bot=True, asn=15169, country="US"), "verified"),
])
def test_capture_replays_actual_intel_and_traps_without_network(intel, outcome):
    obs = observation(intel, outcome)
    s, config, context = captured(intel=intel, obs=obs)
    effective = api().validate_runtime_context(s, config, context)
    assert effective["intel"] == asdict(intel)
    assert effective["traps"] == ["/private-trap", "/x"]
    assert effective["provenance"]["observation"] == obs
    assert effective["provenance"]["availability"] == "available"
    assert context["observation"] == obs
    assert "traps" not in context and "trap_paths" not in context
    assert context["captured_at"] == NOW
    from bouncer.db.participants import session_digest as review_digest
    from bouncer.db.store import session_digest
    assert review_digest is session_digest
    assert context["session_digest"] == session_digest(s)


def test_custom_intel_and_disabled_intel_preserve_unknown_provenance():
    for intel, enabled in [(IpIntel(), False), (IpIntel(verified_bot=False), True)]:
        s, config, context = captured(intel=intel, enabled=enabled)
        result = api().validate_runtime_context(s, config, context)
        assert result["intel"] == asdict(intel)
        assert result["provenance"]["availability"] == "unavailable"
        assert result["provenance"]["intel_enabled"] is enabled
        assert result["provenance"]["observation"] is None


@pytest.mark.parametrize("field,value", [
    ("verified_bot", 1), ("asn", True), ("asn", 0), ("asn", 2**32),
    ("asn_type", "hosting"), ("country", "us"), ("country", "secret"),
])
def test_invalid_intel_capture_is_unavailable(field, value):
    s, config, context = captured(intel=replace(IpIntel(), **{field: value}))
    assert context["available"] is False
    with pytest.raises(ValueError):
        api().validate_runtime_context(s, config, context)


@pytest.mark.parametrize("change", [
    {"session_digest": "0" * 64}, {"trap_config_version": "0" * 64},
    {"captured_at": "2026-11-14T00:01:00"}, {"intel_enabled": 1},
    {"intel": {"verified_bot": 1}}, {"prediction": "human"},
    {"observation": observation(IpIntel(verified_bot=True), "mismatch")},
    {"observation": observation(IpIntel(verified_bot=False), "mismatch")},
    {"observation": observation() | {"resolver_outcome": "secret"}},
    {"observation": observation() | {"checked_at": "2026-11-14T00:01:00"}},
    {"observation": observation() | {"checked_at": "2026-11-14T00:02:00+00:00"}},
])
def test_tampered_context_is_rejected(change):
    s, config, context = captured()
    context.update(change)
    with pytest.raises(ValueError):
        api().validate_runtime_context(s, config, context)


def test_digest_and_configuration_are_exact():
    s, config, context = captured()
    with pytest.raises(ValueError):
        api().validate_runtime_context(replace(s, requests=s.requests * 2), config, context)
    for bad in [config | {"trap_paths": ["/other"]}, config | {"extra": True}]:
        with pytest.raises(ValueError):
            api().validate_runtime_context(s, bad, context)


def test_effective_context_revalidates_session_configuration_and_provenance():
    s, config, context = captured(obs=observation())
    effective = api().validate_runtime_context(s, config, context)
    arguments = dict(session_digest=context["session_digest"],
                     config_digest=config["trap_config_version"], captured_at=NOW)
    assert api().validate_effective_context(s, effective, **arguments) == effective
    unavailable = effective["provenance"] | {"availability": "unavailable"}
    for bad in [effective | {"extra": True}, effective | {"traps": ["/other"]},
                effective | {"provenance": unavailable},
                effective | {"intel": asdict(IpIntel(verified_bot=False))}]:
        with pytest.raises(ValueError):
            api().validate_effective_context(s, bad, **arguments)
    with pytest.raises(ValueError):
        api().validate_effective_context(replace(s, requests=s.requests * 2),
                                         effective, **arguments)


def test_unsafe_non_json_context_validation_raises_value_error():
    s, config, context = captured()
    context["intel"]["country"] = {"unsafe"}
    with pytest.raises(ValueError):
        api().validate_runtime_context(s, config, context)


@pytest.mark.parametrize("traps", [frozenset(f"/{n}" for n in range(129)),
                                   frozenset({"/" + "é" * 1024})])
def test_oversized_optional_configuration_is_unavailable(traps):
    config = api().capture_configuration(traps)
    assert config["available"] is False
    context = api().capture_session(session(), IpIntel(), configuration=config,
                                    captured_at=NOW, intel_enabled=False, observation=None)
    assert context["available"] is False


def test_context_map_budget_never_silently_truncates():
    s, config, context = captured()
    assert api().bound_contexts({s.id: context}) == {s.id: context}
    for contexts in [{str(n): context for n in range(6001)},
                     {"x": context | {"extra": "x" * (2 * 1024**2)}}]:
        result = api().bound_contexts(contexts)
        assert result == {"available": False, "reason": "runtime_context_budget_exceeded"}


def test_worker_captures_exact_score_inputs_and_public_view_hides_capture(tmp_path, monkeypatch):
    from bouncer.api.investigations import public_legacy
    from bouncer.ingest import worker
    from tests.a.test_worker import _rec, _write

    log = tmp_path / "access.log"
    _write(log, [_rec(1794614400, "192.0.2.1")], "w")
    actual = IpIntel(verified_bot=False, asn=123, asn_type="datacenter", country="FI")
    scored = []
    original = worker.score

    def score(s, intel, camp, **kwargs):
        scored.append((s, intel, kwargs["traps"]))
        return original(s, intel, camp, **kwargs)

    monkeypatch.setattr(worker, "score", score)
    w = worker.Worker(log, tmp_path / "snapshot.json", secret=None,
                      intel_fn=lambda ip: actual, campaigns_fn=None, synthetic=True,
                      traps=frozenset({"/private-trap"}))
    payload = w.cycle()
    config = payload["runtime_configuration"]
    for s, intel, traps in scored:
        context = payload["runtime_contexts"][s.id]
        effective = api().validate_runtime_context(s, config, context)
        assert effective["intel"] == asdict(intel)
        assert effective["traps"] == sorted(traps)
        assert context["captured_at"] == payload["ingest"]["updated_at"]
    assert "runtime_contexts" not in public_legacy(payload)
    assert "private-trap" not in json.dumps(public_legacy(payload))
    assert json.loads((tmp_path / "snapshot.json").read_text())["runtime_configuration"] == config
    w.trap_paths = frozenset(f"/{n}" for n in range(129))
    assert len(w.cycle()["sessions"]) == 1
    assert w.cycle()["runtime_configuration"]["available"] is False


def test_worker_preserves_live_observations_before_intel_cache_eviction(tmp_path):
    from bouncer.ingest.worker import Worker
    from bouncer.network.live import LiveIntel
    from tests.a.test_worker import _rec, _write

    log = tmp_path / "access.log"
    _write(log, [_rec(1794614400, "192.0.2.1"), _rec(1794614401, "192.0.2.2")], "w")
    intel = IpIntel(verified_bot=True, asn=15169, country="US")
    live = LiveIntel(runner=lambda ip, timeout: json.dumps(
        observation(intel, "verified")).encode(), cache_size=1)
    payload = Worker(log, tmp_path / "snapshot.json", secret=None, intel_fn=live,
                     campaigns_fn=None, synthetic=False, traps=frozenset()).cycle()
    assert len(payload["runtime_contexts"]) == 2
    for raw in payload["sessions"]:
        s = _session_from_dict(raw)
        context = payload["runtime_contexts"][s.id]
        assert context["observation"] == payload["ip_evidence"][s.ip]
        effective = api().validate_runtime_context(s, payload["runtime_configuration"], context)
        assert effective["intel"] == asdict(intel)


def test_import_analyzer_discards_native_runtime_capture_fields():
    from bouncer.ingest.import_analysis import analyze_records
    from tests.a.test_import_analysis import record

    snapshot = analyze_records([record()], False)
    assert "runtime_contexts" not in snapshot
    assert "runtime_configuration" not in snapshot


def test_sql_worker_capture_is_unavailable_when_approved_full_history_exceeds_view(
    study, tmp_path,  # noqa: F811
):
    from bouncer.ingest.worker import Worker
    from tests.a.test_worker import _rec, _write

    store, repo = study
    log = tmp_path / "access.log"
    timestamp = datetime(2026, 11, 14, tzinfo=UTC).timestamp()
    _write(log, [_rec(timestamp, "192.0.2.1"), _rec(timestamp + 1, "192.0.2.1")], "w")
    w = Worker(log, tmp_path / "unused.json", secret=None, intel_fn=None,
               campaigns_fn=None, synthetic=False, traps=frozenset({"/private-trap"}),
               repository=repo, source_key="collection-a", max_records=2)
    first = w.cycle()
    enrolled = enroll(store)
    sid = first["sessions"][0]["id"]
    review(store, enrolled, external_session_id=sid)
    approved = store.load_approved(["collection-a"])[0]
    assert approved.provenance["source"]["runtime_context"]["availability"] == "available"
    saved = repo.load_snapshot("collection-a")
    assert saved["runtime_contexts"] == first["runtime_contexts"]
    _write(log, [_rec(timestamp + 2, "192.0.2.1")])
    w.cycle()
    assert store.load_approved(["collection-a"]) == []
    review(store, enrolled, external_session_id=sid, expected_revision=1)
    approved = store.load_approved(["collection-a"])[0]
    assert len(approved.session.requests) == 3
    assert approved.provenance["source"]["runtime_context"]["availability"] == "unavailable"
    _write(log, [_rec(timestamp + 3, "192.0.2.2"), _rec(timestamp + 4, "192.0.2.2")])
    w.cycle()
    assert store.load_approved(["collection-a"])[0].provenance["source"]["runtime_context"] == {
        "availability": "unavailable", "reason": "runtime_context_unavailable",
    }


@pytest.mark.parametrize("mode", ["exact", "truncated", "missing", "import", "budget"])
def test_current_approved_full_session_binds_current_snapshot_context(study, mode):  # noqa: F811
    store, repo = study
    s = source(repo, count=2)
    enrolled = enroll(store)
    review(store, enrolled)
    s, config, context = captured(s if mode != "truncated" else replace(s, requests=s.requests[:1]))
    with repo.engine.begin() as conn:
        snapshot = deepcopy(conn.scalar(select(sources.c.snapshot)))
        if mode != "missing":
            snapshot.update(runtime_configuration=config, runtime_contexts={s.id: context})
        if mode == "import":
            snapshot["trap_policy"] = "unavailable_for_import"
        if mode == "budget":
            snapshot["runtime_contexts"] = api().bound_contexts(
                {str(n): context for n in range(6001)})
        conn.execute(update(sources).values(snapshot=snapshot))
    approved = store.load_approved(["collection-a"])[0]
    result = approved.provenance["source"]["runtime_context"]
    assert result["availability"] == ("available" if mode == "exact" else "unavailable")
    packet = store.inspect_session(enrollment_id=enrolled["enrollment_id"],
                                   external_session_id=s.id)
    assert packet["source"]["runtime_context"] == result
    if mode == "exact":
        assert result["effective"]["intel"] == asdict(IpIntel())
        assert result["config_digest"] == config["trap_config_version"]
        assert result["session_digest"] == approved.digest
        assert result["captured_at"] == NOW
        assert _session_from_dict(packet["session"]) == approved.session
