from fastapi.testclient import TestClient

from bouncer.api.app import app


def test_published_evaluation_is_explicitly_synthetic_and_preserves_denominators():
    response = TestClient(app).get("/api/evaluation")
    assert response.status_code == 200
    report = response.json()
    assert report["synthetic"] is True
    assert report["dataset"]["split"] == "reserved_known_templates"
    for value in report["metrics"].values():
        assert 0 <= value["numerator"] <= value["denominator"] <= report["dataset"]["n_sessions"]
        assert value["ci95_lower"] <= value["value"] + 1e-12
        assert value["value"] <= value["ci95_upper"] + 1e-12
    assert "independent_real_humans" in report["unavailable"]


def test_missing_or_invalid_report_cannot_become_a_measured_success(tmp_path, monkeypatch):
    from bouncer.api import evaluation

    path = tmp_path / "report.json"
    monkeypatch.setattr(evaluation, "REPORT_PATH", path)
    assert TestClient(app).get("/api/evaluation").json()["available"] is False
    path.write_text('{"available":true,"synthetic":false,"private":"do-not-publish"}')
    response = TestClient(app).get("/api/evaluation")
    assert response.status_code == 503
    assert "do-not-publish" not in response.text
