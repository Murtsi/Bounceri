"""Bounded private capture of native score inputs; validation performs no lookups."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime

from bouncer.contracts import IpIntel, Session
from bouncer.db.store import session_digest

CONFIG_SCHEMA = "native-runtime-config-v1"
CONTEXT_SCHEMA = "native-runtime-context-v1"
MAX_CONTEXTS = 6000
MAX_CONTEXT_BYTES = 2 * 1024**2
_INTEL_FIELDS = {"verified_bot", "asn", "asn_type", "country"}
_OBSERVATION_FIELDS = _INTEL_FIELDS | {
    "checked_at", "resolver_outcome", "crawler", "asn_origin",
}


def _encoded(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, OverflowError, RecursionError):
        raise ValueError("unsafe runtime capture serialization") from None


def _utc(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid runtime timestamp")
    dt = datetime.fromisoformat(value)
    if dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("runtime timestamp must be UTC")
    return dt


def _traps(traps):
    if not isinstance(traps, (set, frozenset, list, tuple)) or len(traps) > 128:
        raise ValueError("invalid runtime trap configuration")
    for path in traps:
        if (not isinstance(path, str) or not path.startswith("/")
                or any(char in path for char in ("\x00", "\n", "\r"))
                or len(path.encode("utf-8")) > 2048):
            raise ValueError("invalid runtime trap path")
    paths = sorted(traps)
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate runtime trap path")
    return paths


def _config(configuration):
    if (not isinstance(configuration, dict) or configuration.keys() != {
        "schema_version", "available", "trap_paths", "trap_config_version",
    } or configuration["schema_version"] != CONFIG_SCHEMA
            or configuration["available"] is not True):
        raise ValueError("runtime_configuration_unavailable")
    paths = _traps(configuration["trap_paths"])
    digest = hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()
    if configuration["trap_paths"] != paths or configuration["trap_config_version"] != digest:
        raise ValueError("runtime_configuration_invalid")
    return paths


def capture_configuration(traps) -> dict:
    """Store the exact local trap configuration once, or an explicit fixed failure."""
    try:
        paths = _traps(traps)
        return {"schema_version": CONFIG_SCHEMA, "available": True, "trap_paths": paths,
                "trap_config_version": hashlib.sha256("\n".join(paths).encode()).hexdigest()}
    except (ValueError, TypeError, OverflowError, RecursionError):
        return {"schema_version": CONFIG_SCHEMA, "available": False,
                "reason": "runtime_configuration_invalid_or_oversized"}


def _intel(value):
    if not isinstance(value, dict) or value.keys() != _INTEL_FIELDS:
        raise ValueError("invalid runtime intel fields")
    verified, asn, country = value["verified_bot"], value["asn"], value["country"]
    if verified is not None and type(verified) is not bool:
        raise ValueError("invalid runtime bot verification")
    if asn is not None and (type(asn) is not int or not 0 < asn <= 4294967295):
        raise ValueError("invalid runtime ASN")
    if value["asn_type"] not in ("unknown", "datacenter", "residential", "mobile"):
        raise ValueError("invalid runtime ASN type")
    if country is not None and (not isinstance(country, str) or len(country) != 2
                               or not country.isascii() or not country.isalpha()
                               or not country.isupper()):
        raise ValueError("invalid runtime country")
    return value.copy()


def _observation(value, intel, captured_at):
    if value is None:
        return None
    if not isinstance(value, dict) or value.keys() != _OBSERVATION_FIELDS:
        raise ValueError("invalid runtime observation fields")
    if _intel({key: value[key] for key in _INTEL_FIELDS}) != intel:
        raise ValueError("runtime observation differs from score inputs")
    checked_at = _utc(value["checked_at"])
    if checked_at > captured_at:
        raise ValueError("runtime observation is after capture")
    verified = intel["verified_bot"]
    expected = ("verified",) if verified is True else (("mismatch",) if verified is False else (
        "unavailable", "timeout", "capacity", "invalid",
    ))
    if value["resolver_outcome"] not in expected:
        raise ValueError("inconsistent runtime resolver status")
    if ((verified is True and value["crawler"] not in ("googlebot", "bingbot"))
            or (verified is not True and value["crawler"] is not None)):
        raise ValueError("inconsistent runtime crawler")
    if value["asn_origin"] not in ("curated-prefix", "inferred", "unknown"):
        raise ValueError("invalid runtime ASN origin")
    if (value["asn_origin"] == "curated-prefix" and intel["asn"] is None
            or value["asn_origin"] == "unknown" and intel["asn"] is not None):
        raise ValueError("inconsistent runtime ASN origin")
    return value.copy()


def validate_runtime_context(session: Session, configuration, context) -> dict:
    """Return private JSON-ready score inputs bound to this exact full session."""
    paths = _config(configuration)
    if (not isinstance(context, dict) or context.keys() != {
        "schema_version", "available", "session_digest", "captured_at", "trap_config_version",
        "intel", "intel_enabled", "observation",
    } or context["schema_version"] != CONTEXT_SCHEMA or context["available"] is not True):
        raise ValueError("runtime_context_unavailable")
    if len(_encoded(context)) > 16 * 1024:
        raise ValueError("runtime_context_oversized")
    if context["session_digest"] != session_digest(session):
        raise ValueError("runtime_session_digest_mismatch")
    if context["trap_config_version"] != configuration["trap_config_version"]:
        raise ValueError("runtime_configuration_digest_mismatch")
    captured_at = _utc(context["captured_at"])
    if type(context["intel_enabled"]) is not bool:
        raise ValueError("invalid runtime intel enabled flag")
    intel = _intel(context["intel"])
    observation = _observation(context["observation"], intel, captured_at)
    if not context["intel_enabled"] and (observation is not None or intel != asdict(IpIntel())):
        raise ValueError("disabled runtime intel has evidence")
    return {"intel": intel, "traps": paths, "provenance": {
        "availability": "available" if observation is not None else "unavailable",
        "intel_enabled": context["intel_enabled"], "observation": observation,
    }}


def capture_session(session: Session, intel: IpIntel, *, configuration, captured_at,
                    intel_enabled, observation) -> dict:
    """Optional capture failure must never discard otherwise valid traffic."""
    try:
        context = {"schema_version": CONTEXT_SCHEMA, "available": True,
                   "session_digest": session_digest(session), "captured_at": captured_at,
                   "trap_config_version": configuration.get("trap_config_version"),
                   "intel": asdict(intel), "intel_enabled": intel_enabled,
                   "observation": observation.copy() if isinstance(observation, dict)
                   else observation}
        validate_runtime_context(session, configuration, context)
        return context
    except (ValueError, TypeError, AttributeError, OverflowError, RecursionError):
        return {"schema_version": CONTEXT_SCHEMA, "available": False,
                "reason": "runtime_context_invalid_or_unavailable"}


def validate_effective_context(session: Session, effective, *, session_digest,
                               config_digest, captured_at) -> dict:
    """Recheck private extracted evidence at the isolated replay protocol boundary."""
    if (not isinstance(effective, dict) or effective.keys() != {"intel", "traps", "provenance"}
            or not isinstance(effective["provenance"], dict)
            or effective["provenance"].keys() != {
                "availability", "intel_enabled", "observation",
            }):
        raise ValueError("invalid effective runtime context")
    provenance = effective["provenance"]
    result = validate_runtime_context(session, {
        "schema_version": CONFIG_SCHEMA, "available": True,
        "trap_paths": effective["traps"], "trap_config_version": config_digest,
    }, {
        "schema_version": CONTEXT_SCHEMA, "available": True,
        "session_digest": session_digest, "captured_at": captured_at,
        "trap_config_version": config_digest, "intel": effective["intel"],
        "intel_enabled": provenance["intel_enabled"], "observation": provenance["observation"],
    })
    if result != effective:
        raise ValueError("inconsistent effective runtime provenance")
    return result


def bound_contexts(contexts) -> dict:
    """Reject the whole optional capture instead of presenting truncation as complete."""
    try:
        if (not isinstance(contexts, dict) or len(contexts) > MAX_CONTEXTS
                or len(_encoded(contexts)) > MAX_CONTEXT_BYTES):
            raise ValueError
        return contexts
    except (ValueError, TypeError, OverflowError, RecursionError):
        return {"available": False, "reason": "runtime_context_budget_exceeded"}
