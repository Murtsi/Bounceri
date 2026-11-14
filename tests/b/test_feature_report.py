from bouncer.contracts import SessionLabel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.feature_report import feature_report

from .synthetic import CHROME_PAGE_HEADERS, req, session


def test_unavailable_headers_are_missing_without_mutating_dataset():
    imported = session([req(0, "/")], sid="imported")
    observed = session([req(1, "/", headers=CHROME_PAGE_HEADERS)], sid="observed")
    ds = build_dataset([imported, observed], [])
    original_features = list(ds.unlabeled)

    report = feature_report(ds, unavailable_fields={"imported": ["headers"]})

    header = report["groups"]["real/unlabeled"]["header_inconsistency_share"]
    assert header == {"n": 2, "missing": 1, "p10": 0.0, "median": 0.0, "p90": 0.0}
    assert ds.unlabeled == original_features
    assert ds.unlabeled[0][1].header_inconsistency_share == 1.0


def test_unavailable_ua_and_content_type_have_no_observed_feature_values():
    imported = session([req(0, "/", ua="")], ua="", sid="imported")
    ds = build_dataset([imported], [SessionLabel("imported", "run", "human")])

    report = feature_report(
        ds, unavailable_fields={"imported": ["user_agent", "content_type"]}
    )

    features = report["groups"]["simulated/human"]
    for name in ("ua_is_tool", "ua_claims_bot", "static_share", "html_share",
                 "header_inconsistency_share"):
        assert features[name] == {"n": 1, "missing": 1}
    assert features["n_requests"]["missing"] == 0


def test_unlabeled_origin_does_not_override_labeled_row_origins():
    unlabeled = session([req(0, "/")], sid="unlabeled")
    trapped = session([req(1, "/trap")], sid="trapped")
    ds = build_dataset([unlabeled, trapped], [], traps=frozenset({"/trap"}))

    report = feature_report(ds, unlabeled_origin="simulated")

    assert set(report["groups"]) == {"simulated/unlabeled", "real/bad_bot"}
