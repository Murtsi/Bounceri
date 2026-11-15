import csv
import hashlib
import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bouncer.api.app import app
from tools.datasets import reply_attacks as reply


def write_source(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["poster_tweetid", "tweet_label", "mean_cosine", "50%_diff_min", "org_reply_count"]
        )
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_checksum_dedupe_and_partition(tmp_path):
    path = tmp_path / "source.csv"
    digest = write_source(path, [("private-a", 0, 0.1, 1, 5), ("private-a", 0, 0.2, 1, 5)])
    rows, counts = reply.load_source(path, digest)
    assert len(rows) == 1 and counts["duplicate_id_rows"] == 1
    assert rows[0]["mean_cosine"] == 0.1
    assert reply.partition("private-a") == reply.partition("private-a")
    with pytest.raises(ValueError, match="checksum"):
        reply.load_source(path, "0" * 64)
    digest = write_source(path, [("a", 0, 0.1, 1, 5), ("a", 1, 0.1, 1, 5)])
    with pytest.raises(ValueError, match="conflicting"):
        reply.load_source(path, digest)
    digest = write_source(path, [("a", 0, "nan", 1, 5)])
    with pytest.raises(ValueError, match="finite"):
        reply.load_source(path, digest)


def test_stump_uses_only_training_and_metrics_have_real_denominators():
    train = [
        {"mean_cosine": x, "tweet_label": y} for x, y in [(0.0, 0), (0.1, 0), (0.8, 1), (1.0, 1)]
    ]
    stump = reply.fit_stump(train)
    assert stump == reply.fit_stump(list(reversed(train)))
    assert stump == (">=", 0.8)
    measured = reply.measure(train, stump)
    assert measured["precision"]["denominator"] == 2
    assert measured["recall"]["numerator"] == 2
    assert measured["false_positive_rate"]["denominator"] == 2
    assert measured["abstention_rate"]["denominator"] == 4
    assert measured["abstentions"] == 0


def test_heldout_labels_cannot_change_the_stump_or_membership(monkeypatch):
    rows = [
        {
            "id": f"private-{i}",
            "tweet_label": i % 2,
            "mean_cosine": float(i % 2),
            "50%_diff_min": 1.0,
            "org_reply_count": 5.0,
        }
        for i in range(100)
    ]
    monkeypatch.setattr(reply, "load_source", lambda path: (rows, {}))
    before = reply.build_report(Path("unused"))
    for row in rows:
        if reply.partition(row["id"]) != "train":
            row["tweet_label"] = 1 - row["tweet_label"]
    after = reply.build_report(Path("unused"))
    assert before["baseline"] == after["baseline"]
    assert before["reproducibility"] == after["reproducibility"]
    assert before["splits"]["test"] != after["splits"]["test"]


def test_missing_feature_is_rejected_and_undefined_rates_are_null(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("poster_tweetid,tweet_label\na,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required feature"):
        reply.load_source(path, hashlib.sha256(path.read_bytes()).hexdigest())
    measured = reply.measure([{"mean_cosine": 0.1, "tweet_label": 0}], (">=", 0.5))
    assert measured["precision"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
        "ci95_lower": None,
        "ci95_upper": None,
    }


def test_public_report_is_aggregate_only_and_invalid_report_is_unavailable(tmp_path, monkeypatch):
    from bouncer.api import social_preview

    def no_network(*args, **kwargs):
        raise AssertionError("aggregate endpoint must not call a provider")

    monkeypatch.setattr(socket, "create_connection", no_network)
    client = TestClient(app)
    response = client.get("/api/evaluation/social-replies")
    assert response.status_code == 200
    report = response.json()
    assert report["scope"] == "historical_tweet_targeting_research"
    assert report["dataset"]["unique_posts"] == 7732
    assert "poster_tweetid" not in response.text
    assert "raw_rows" in report["dataset"]
    path = tmp_path / "report.json"
    monkeypatch.setattr(social_preview, "REPORT_PATH", path)
    assert client.get("/api/evaluation/social-replies").status_code == 503
    report["private_rows"] = [{"poster_tweetid": "PRIVATE-CANARY"}]
    path.write_text(json.dumps(report), encoding="utf-8")
    response = client.get("/api/evaluation/social-replies")
    assert response.status_code == 503
    assert "PRIVATE-CANARY" not in response.text
    del report["private_rows"]
    report["splits"]["test"]["confusion"]["fp"] += 1
    path.write_text(json.dumps(report), encoding="utf-8")
    assert client.get("/api/evaluation/social-replies").status_code == 503
    path.write_bytes(b" " * (social_preview.MAX_REPORT_BYTES + 1))
    assert client.get("/api/evaluation/social-replies").status_code == 503
