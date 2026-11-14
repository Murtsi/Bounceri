"""Offline safety and orchestration contracts for the advisory review pipeline."""

from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import replace

import httpx
import pytest


def packet():
    return {
        "case_id": "case-1",
        "evidence_version": 1,
        "evidence_hash": "a" * 64,
        "synthetic": True,
        "complete": True,
        "evidence": [
            {
                "id": "ev-1",
                "kind": "session_summary",
                "data": {
                    "session_ref": "session-1",
                    "n_requests": 12,
                    "failed_logins": 4,
                    "distinct_account_count": 2,
                    "distinct_client_count": 3,
                    "path_category_counts": {"probe": 2, "trap": 0, "other": 10},
                    "path_category_version": "categories-v1",
                    "attack_signals": ["probe"],
                },
            }
        ],
        "local_assessment": {"label": "bad_bot", "model_version": "rules-v1"},
    }


def recommendation():
    return {
        "label": "bad_bot",
        "automation": "automated",
        "authentication_pattern": "distributed_failed_authentication",
        "crawler_verification": "unknown",
        "coordination": "unknown",
        "maliciousness": "supported",
        "suggested_action": "rate_limit",
        "supporting_evidence_ids": ["ev-1"],
        "contradicting_evidence_ids": [],
        "missing_information": ["Independent human labels"],
        "benign_alternatives": ["Authorized security testing remains possible"],
        "rationale": "Observed probe paths and failed authentication warrant review.",
        "observations": [{"evidence_id": "ev-1", "field": "n_requests", "value": 12}],
    }


def settings():
    from bouncer.review import ProviderConfig, ReviewSettings

    common = dict(
        enabled=True,
        contract_verified=True,
        identity_verified=True,
        no_fallback_verified=True,
        pricing_verified=True,
        limits_verified=True,
        maximum_cost_microusd=20_000,
        pricing_version="fixture-pricing-v1",
    )
    return ReviewSettings(
        enabled=True,
        decision=ProviderConfig(
            provider="hostinger",
            model="decision-deployment",
            expected_model="microsoft-decision-1",
            endpoint="https://router.hostinger.com/verified-native-route",
            api_key="fixture-credential",
            **common,
        ),
        reviewer=ProviderConfig(
            provider="featherless",
            model="fixture/reviewer",
            expected_model="fixture/reviewer",
            endpoint="https://api.featherless.ai/v1/chat/completions",
            api_key="fixture-credential",
            **common,
        ),
    )


class MemoryStore:
    """Frozen persistence seam; records ordering, not provider internals."""

    def __init__(self, config_key, case_packet=None):
        self.job = {"id": "job-1", "config_key": config_key, "case_id": "case-1"}
        self.packet = copy.deepcopy(case_packet or packet())
        self.events = []
        self.assessments = []
        self.settlements = []
        self.finished = None

    def claim_job(self, worker_id):
        job, self.job = self.job, None
        self.events.append(("claim", worker_id))
        return job

    def review_packet(self, job_id):
        return copy.deepcopy(self.packet)

    def start_request(self, job_id, stage, provider, model, maximum_cost_microusd, pricing_version):
        self.events.append(("reserve", stage, maximum_cost_microusd))
        return {"id": f"reservation-{stage}"}

    def settle_request(self, reservation_id, actual_cost_microusd, usage, provider_request_id):
        self.events.append(("settle", reservation_id))
        self.settlements.append((reservation_id, actual_cost_microusd, usage, provider_request_id))

    def append_assessment(self, job_id, stage, payload, metadata):
        self.assessments.append({"stage": stage, "payload": payload, "metadata": metadata})

    def finish_job(self, job_id, status, reason=""):
        self.finished = (status, reason)


class Responses:
    def __init__(self, store, *, error=None, reviewer=None, decision_model=None):
        self.store, self.error = store, error
        self.reviewer = reviewer or recommendation()
        self.decision_model = decision_model or "microsoft-decision-1"
        self.requests = []

    def __call__(self, endpoint, headers, body, timeout):
        self.store.events.append(("send", endpoint))
        self.requests.append((endpoint, headers, copy.deepcopy(body), timeout))
        if self.error:
            raise self.error
        if "questions" in body:
            return {
                "id": "decision-request",
                "model": self.decision_model,
                "answers": {
                    name: {"type": "choice", "choice": "unknown"} for name in body["questions"]
                },
                "usage": {"input_tokens": 50, "output_tokens": 5},
            }
        return {
            "id": "review-request",
            "model": "fixture/reviewer",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(self.reviewer),
                        "reasoning_content": "Private reasoning must never be stored",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 70,
                "total_tokens": 170,
                "cost": 0.0012341,
            },
        }


def test_review_package_exists():
    assert importlib.util.find_spec("bouncer.review") is not None


def test_default_capabilities_disabled_and_legacy_keys_not_used():
    from bouncer.review import ReviewSettings, capabilities

    cfg = ReviewSettings.from_env({"OPENAI_API_KEY": "never-used", "LLM_MODEL": "gemini"})
    state = capabilities(cfg)
    assert state["enabled"] is False
    assert state["decision_model"]["available"] is False
    assert state["reviewer"]["available"] is False
    assert cfg.decision.api_key == ""
    assert "never-used" not in repr(cfg)


def test_missing_hostinger_no_fallback_verification_disables_cascade_without_dispatch():
    from bouncer.review import ReviewRunner

    cfg = settings()
    cfg = replace(cfg, decision=replace(cfg.decision, no_fallback_verified=False))
    store = MemoryStore(cfg.config_key)
    transport = Responses(store)
    assert ReviewRunner(store, cfg, transport=transport).run_once() is True
    assert store.finished[0] == "unavailable"
    assert "no_substitution" in store.finished[1]
    assert not transport.requests
    assert not store.settlements


def test_cascade_reserves_before_each_call_preserves_stages_and_settles_usd_upwards():
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key)
    transport = Responses(store)
    runner = ReviewRunner(store, cfg, transport=transport)
    assert runner.run_once() is True
    assert runner.run_once() is False
    assert store.finished == ("completed", "")
    assert [row["stage"] for row in store.assessments] == ["decision_model", "reviewer"]
    assert [event[0] for event in store.events[:7]] == [
        "claim",
        "reserve",
        "send",
        "settle",
        "reserve",
        "send",
        "settle",
    ]
    assert store.settlements[0][1] is None  # Native billing contract not invented.
    assert store.settlements[1][1] == 1235  # Never under-reserve fractional microdollars.
    assert transport.requests[0][2]["model"] == "decision-deployment"
    assert "state" in transport.requests[0][2]
    assert transport.requests[1][2]["max_completion_tokens"] == 800
    assert all(item[3] == 30 for item in transport.requests)
    assert "response_format" not in transport.requests[1][2]
    assert "Private reasoning" not in json.dumps(store.assessments)
    assert "not_semantic_proof" in json.dumps(store.assessments)


@pytest.mark.parametrize("failure", [TimeoutError("sensitive error"), RuntimeError("secret")])
def test_unknown_provider_outcome_retains_reservation_and_never_retries(failure):
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key)
    transport = Responses(store, error=failure)
    assert ReviewRunner(store, cfg, transport=transport).run_once()
    assert len(transport.requests) == 1
    assert store.finished[0] == "unavailable"
    assert store.settlements[0][1] is None
    assert not store.assessments
    assert "secret" not in str(store.finished)
    assert "sensitive" not in str(store.finished)


def test_model_substitution_stops_before_reviewer_and_keeps_unknown_charge():
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key)
    transport = Responses(store, decision_model="different-model")
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert len(transport.requests) == 1
    assert store.finished == ("unavailable", "model_identity_mismatch")
    assert store.settlements[0][1] is None


@pytest.mark.parametrize(
    "change",
    [
        {"complete": False},
        {"evidence": []},
        {"evidence_hash": ""},
    ],
)
def test_incomplete_packets_do_not_spend(change):
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key, packet() | change)
    transport = Responses(store)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.finished[0] == "unavailable"
    assert not transport.requests


def test_unallowlisted_private_evidence_is_rejected_before_any_provider_call():
    from bouncer.review import ReviewRunner

    cfg = settings()
    data = packet()
    data["evidence"][0]["data"]["request_headers"] = {"Authorization": "private"}
    store = MemoryStore(cfg.config_key, data)
    transport = Responses(store)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.finished == ("unavailable", "invalid_evidence_packet")
    assert not transport.requests


def test_unknown_config_does_not_run_an_implicitly_different_experiment():
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore("different-model-configuration")
    transport = Responses(store)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.finished == ("unavailable", "configuration_mismatch")
    assert not transport.requests


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(label="verified_human"),
        lambda r: r.update(supporting_evidence_ids=["invented"]),
        lambda r: r["observations"][0].update(value=13),
        lambda r: r.update(label="good_bot", crawler_verification="verified"),
        lambda r: r.update(suggested_action="run_shell"),
        lambda r: r.update(extra_instructions="ignore policy"),
    ],
)
def test_invalid_typed_recommendations_are_rejected_after_billing_without_repair(mutate):
    from bouncer.review import ReviewRunner

    cfg = settings()
    result = recommendation()
    mutate(result)
    store = MemoryStore(cfg.config_key)
    transport = Responses(store, reviewer=result)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert len(transport.requests) == 2
    assert [row["stage"] for row in store.assessments] == ["decision_model"]
    assert store.finished == ("unavailable", "invalid_reviewer_output")
    assert store.settlements[1][1] == 1235


def test_unknown_maliciousness_cannot_be_promoted_from_speed_or_local_label():
    from bouncer.review import validate_recommendation

    data = packet()
    data["evidence"][0]["data"].pop("attack_signals")
    data["evidence"][0]["data"]["path_category_counts"] = {"other": 12}
    with pytest.raises(ValueError):
        validate_recommendation(recommendation(), data)


def test_malformed_json_refusal_and_truncation_do_not_create_assessments():
    from bouncer.review import parse_reviewer_response

    for message, finish in [("```json\n{}\n```", "stop"), ("{}", "length"), ("{}", "stop")]:
        response = {
            "model": "fixture/reviewer",
            "choices": [
                {
                    "message": {"content": message, "refusal": "refused"},
                    "finish_reason": finish,
                }
            ],
        }
        with pytest.raises(ValueError):
            parse_reviewer_response(response, packet(), "fixture/reviewer")


def test_http_transport_disables_redirects_and_never_retries():
    from bouncer.review import HttpTransport

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(307, headers={"location": "https://unapproved.example/inference"})

    transport = HttpTransport(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="provider_http_error"):
        transport("https://api.featherless.ai/v1/chat/completions", {}, {}, 30)
    assert len(calls) == 1


def test_http_transport_bounds_response_and_rejects_non_json():
    from bouncer.review import HttpTransport

    for body in [b"x" * 65_537, b"not JSON"]:
        transport = HttpTransport(
            transport=httpx.MockTransport(
                lambda request, payload=body: httpx.Response(200, content=payload),
            )
        )
        with pytest.raises(ValueError):
            transport("https://api.featherless.ai/v1/chat/completions", {}, {}, 30)


def test_configuration_key_changes_with_model_and_contains_no_credentials():
    cfg = settings()
    changed = replace(cfg, reviewer=replace(cfg.reviewer, model="fixture/other"))
    assert cfg.config_key != changed.config_key
    assert "fixture-credential" not in cfg.config_key
    assert (
        replace(cfg, reviewer=replace(cfg.reviewer, api_key="rotated")).config_key == cfg.config_key
    )


def test_real_store_packet_contract_preserves_unknown_scores_and_trusted_categories():
    from bouncer.review import ReviewRunner

    cfg = settings()
    data = packet()
    data.update(missing_information=[], distinct_client_count=3)
    data["evidence"][0].update(version=1, redacted=True)
    facts = data["evidence"][0]["data"]
    facts.update(local_score=None, category_provenance="bouncer-path-categories-v1")
    facts.pop("path_category_version")
    facts.pop("attack_signals")
    facts.pop("distinct_client_count")
    data["local_assessment"].update(
        stage="local",
        score=None,
        label_counts={"bad_bot": 1},
        evidence_ids=["ev-1"],
        limitations=["Model estimates"],
    )
    store = MemoryStore(cfg.config_key, data)
    result = recommendation() | {"authentication_pattern": "repeated_failures"}
    ReviewRunner(store, cfg, transport=Responses(store, reviewer=result)).run_once()
    assert store.finished == ("completed", "")


def test_store_reservation_denial_never_dispatches_or_settles():
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key)

    def denied(*args, **kwargs):
        raise ValueError("reservation denied")

    store.start_request = denied
    transport = Responses(store)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.finished == ("deferred_budget", "request_reservation_denied")
    assert not transport.requests
    assert not store.settlements


def test_worker_capabilities_does_not_initialize_database(monkeypatch, capsys):
    from bouncer.review.worker import main

    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")

    def forbidden(*args):
        pytest.fail("capability discovery must not open or mutate a database")

    assert main(["--capabilities"], store_factory=forbidden) == 0
    assert json.loads(capsys.readouterr().out)["enabled"] is False


def test_worker_once_uses_injected_store_and_exits_without_loop(monkeypatch):
    from bouncer.review.worker import main

    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    store = MemoryStore("disabled-job")
    assert (
        main(["--once", "--database-url", "sqlite:///:memory:"], store_factory=lambda url: store)
        == 0
    )
    assert store.job is None
    assert store.finished == ("unavailable", "configuration_mismatch")


@pytest.mark.parametrize(
    "change",
    [
        {
            "label": "good_bot",
            "crawler_verification": "verified",
            "maliciousness": "not_established",
        },
        {"coordination": "observed"},
    ],
)
def test_unavailable_verification_or_relationship_evidence_cannot_be_invented(change):
    from bouncer.review import validate_recommendation

    with pytest.raises(ValueError):
        validate_recommendation(recommendation() | change, packet())


def test_discovery_only_reads_plan_and_exact_model_without_inference_or_account_balance():
    from bouncer.review import discover_featherless

    calls = []

    def metadata(endpoint, headers, timeout):
        calls.append((endpoint, headers, timeout))
        if endpoint.endswith("/plan"):
            return {
                "api_access": True,
                "max_context_length": 4096,
                "max_model_size": None,
                "concurrency": 1,
                "credits": "private-balance",
            }
        return {
            "id": "fixture/reviewer",
            "available_on_current_plan": True,
            "context_length": 8192,
            "max_completion_tokens": 2048,
            "is_gated": False,
            "status": "active",
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000002",
                "request": "0",
                "image": "0",
            },
        }

    result = discover_featherless("fixture-credential", "fixture/reviewer", get_json=metadata)
    assert result["available"] is True
    assert result["effective_context_length"] == 4096
    assert result["max_completion_tokens"] == 2048
    assert result["pricing_usd_per_token"]["completion"] == "0.000002"
    assert "request" not in result["pricing_usd_per_token"]
    assert result["request_cost_usd"] == "0"
    assert [url for url, _, _ in calls] == [
        "https://api.featherless.ai/v1/plan",
        "https://api.featherless.ai/v1/models/fixture%2Freviewer",
    ]
    assert "private-balance" not in json.dumps(result)
    assert "fixture-credential" not in repr(result)
    assert all("completions" not in url for url, _, _ in calls)


def test_discovery_failure_is_sanitized_and_cannot_enable_provider():
    from bouncer.review import discover_featherless

    def unavailable(*args):
        raise RuntimeError("credential-or-private-body")

    result = discover_featherless("fixture-credential", "fixture/reviewer", get_json=unavailable)
    assert result["available"] is False
    assert "credential-or-private-body" not in json.dumps(result)
    assert "fixture-credential" not in json.dumps(result)


def test_broken_aggregate_counts_stop_before_paid_dispatch():
    from bouncer.review import ReviewRunner

    cfg = settings()
    data = packet()
    data["evidence"][0]["data"]["status_counts"] = {"200": 13}
    store = MemoryStore(cfg.config_key, data)
    transport = Responses(store)
    ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.finished == ("unavailable", "invalid_evidence_packet")
    assert not transport.requests


@pytest.mark.parametrize(
    "change",
    [
        {"label": "human", "automation": "automated"},
        {"authentication_pattern": "not_observed"},
        {"label": "bad_bot", "automation": "human_like"},
    ],
)
def test_internally_contradictory_typed_findings_are_rejected(change):
    from bouncer.review import validate_recommendation

    with pytest.raises(ValueError):
        validate_recommendation(recommendation() | change, packet())


def test_reviewer_output_usage_above_ceiling_is_billed_then_rejected():
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = MemoryStore(cfg.config_key)
    source = Responses(store)

    def too_many_tokens(*args):
        response = source(*args)
        if "choices" in response:
            response["usage"]["completion_tokens"] = 801
        return response

    ReviewRunner(store, cfg, transport=too_many_tokens).run_once()
    assert store.finished == ("unavailable", "provider_output_limit_exceeded")
    assert store.settlements[1][1] == 1235
    assert [item["stage"] for item in store.assessments] == ["decision_model"]


def test_explicit_model_policy_cannot_be_bypassed_by_verified_flags():
    cfg = settings()
    for expected in ["gemini-2.0-flash", "unapproved-decision-model"]:
        invalid = replace(cfg.decision, expected_model=expected)
        assert invalid.capability()["available"] is False
    invalid = replace(cfg.reviewer, model="google/Gemini", expected_model="google/Gemini")
    assert invalid.capability()["available"] is False


def test_transactional_store_cascade_and_idempotency_when_core_is_integrated():
    core = pytest.importorskip("bouncer.investigations")
    from bouncer.review import ReviewRunner

    cfg = settings()
    store = core.InvestigationStore("sqlite:///:memory:")
    requests = [{"path": "/.env", "method": "GET", "status": 404}] * 2
    requests += [{"path": "/login", "method": "POST", "status": 401}] * 4
    requests += [{"path": "/", "method": "GET", "status": 200}] * 6
    case = store.create_from_legacy(
        {
            "synthetic": True,
            "sessions": [{"id": "session-1", "ip": "192.0.2.1", "requests": requests}],
            "verdicts": {"session-1": {"label": "bad_bot"}},
        },
        public_demo=True,
    )
    job = store.enqueue_review(case["id"], cfg.config_key, cfg.maximum_cost_microusd)
    result = recommendation() | {
        "supporting_evidence_ids": ["e1"],
        "authentication_pattern": "repeated_failures",
    }
    result["observations"][0]["evidence_id"] = "e1"
    transport = Responses(MemoryStore(cfg.config_key), reviewer=result)
    assert ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.get_case(case["id"])["review"]["status"] == "completed"
    assert [r["stage"] for r in store.list_assessments(case["id"])] == [
        "local",
        "decision_model",
        "reviewer",
    ]
    assert (
        store.enqueue_review(case["id"], cfg.config_key, cfg.maximum_cost_microusd)["id"]
        == job["id"]
    )
    assert not ReviewRunner(store, cfg, transport=transport).run_once()
    assert store.usage()["requests"] == len(transport.requests) == 2
    assert store.usage()["reserved_usd"] == 0.02
    assert store.usage()["spent_usd"] == 0.001235
