import json

from bouncer.eval.metrics import METRICS_PATH, stub_metrics, validate
from bouncer.session import MODEL_VERSION


def test_stub_metrics_matches_schema_and_has_no_numbers():
    m = stub_metrics()
    assert validate(m) == []
    assert m["stub"] is True
    assert m["model_version"] == MODEL_VERSION
    assert m["human_fpr"] is None
    assert m["uncertain_share"] is None


def test_committed_metrics_json_is_the_stub():
    # Ei arviointia vielä (B-7) → levyllä oleva tiedosto on stub nykyiselle versiolle.
    on_disk = json.loads(METRICS_PATH.read_text("utf-8"))
    assert on_disk == stub_metrics()
