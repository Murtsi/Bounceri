import json

from bouncer.eval.metrics import METRICS_PATH, stub_metrics, validate
from bouncer.session import score
from bouncer.session._provisional_types import IpIntel

from .synthetic import human_session


def test_score_stub_is_always_uncertain():
    v = score(human_session(), IpIntel(), None)
    assert v.label == "uncertain"
    assert 0.0 <= v.score <= 1.0
    assert 1 <= len(v.reasons) <= 3
    assert v.model_version == "stub-v0"


def test_score_accepts_missing_network_inputs():
    assert score(human_session(), None, None).label == "uncertain"


def test_stub_metrics_matches_schema_and_has_no_numbers():
    m = stub_metrics()
    assert validate(m) == []
    assert m["stub"] is True
    assert m["human_fpr"] is None
    assert m["uncertain_share"] is None


def test_committed_metrics_json_is_the_stub():
    on_disk = json.loads(METRICS_PATH.read_text("utf-8"))
    assert on_disk == stub_metrics()
