"""Offline historical tweet-targeting preview; emits aggregates, never source rows/IDs.

Run: python -m tools.datasets.reply_attacks SOURCE.csv --output REPORT.json
The predeclared feature and ID split are fixed before fitting; test labels never select a model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import statistics
from collections import defaultdict
from pathlib import Path

SOURCE_SHA256 = "038783083dfad6f8b80949a352044b9eacb65ad1e1cdbbfaebb20e9fd501533f"
FEATURE = "mean_cosine"
SUMMARY_FEATURES = (FEATURE, "50%_diff_min", "org_reply_count")
SPLIT_PREFIX = "bounceri-reply-preview-v1:"


def partition(post_id: str) -> str:
    bucket = int(hashlib.sha256((SPLIT_PREFIX + post_id).encode()).hexdigest(), 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def load_source(path: Path, expected_sha256: str = SOURCE_SHA256) -> tuple[list[dict], dict]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("source checksum mismatch")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    required = {"poster_tweetid", "tweet_label", *SUMMARY_FEATURES}
    if not required.issubset(fields) or len(fields) != len(set(fields)):
        raise ValueError("missing required feature or duplicate column")
    numeric = [key for key in fields if key not in {"poster_tweetid", "tweet_label"}]
    unique = {}
    raw_rows = 0
    for row in reader:
        raw_rows += 1
        post_id = row["poster_tweetid"]
        if not post_id or None in row:
            raise ValueError("invalid source record")
        try:
            label = float(row["tweet_label"])
            values = {key: float(row[key]) for key in numeric}
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("invalid numeric feature") from exc
        if label not in (0, 1) or not all(math.isfinite(value) for value in values.values()):
            raise ValueError("labels must be binary and features finite")
        if post_id in unique:
            if unique[post_id]["tweet_label"] != label:
                raise ValueError("duplicate ID has conflicting label")
            continue
        unique[post_id] = {
            "id": post_id,
            "tweet_label": int(label),
            **{key: values[key] for key in SUMMARY_FEATURES},
        }
    rows = list(unique.values())
    if not rows:
        raise ValueError("empty source")
    return rows, {
        "raw_rows": raw_rows,
        "unique_posts": len(rows),
        "targeted": sum(row["tweet_label"] for row in rows),
        "controls": sum(1 - row["tweet_label"] for row in rows),
        "duplicate_id_rows": raw_rows - len(rows),
        "numeric_features": len(numeric),
    }


def fit_stump(train: list[dict]) -> tuple[str, float]:
    grouped = defaultdict(lambda: [0, 0])
    for row in train:
        grouped[row[FEATURE]][row["tweet_label"]] += 1
    positives = sum(row["tweet_label"] for row in train)
    negatives = len(train) - positives
    if not positives or not negatives:
        raise ValueError("training requires both labels")
    lower_pos = lower_neg = 0
    best_score = -1
    best = None
    # Ascending threshold, then >= before <: deterministic first-tie selection.
    for threshold, (negative, positive) in sorted(grouped.items()):
        for direction, tp, tn in (
            (">=", positives - lower_pos, lower_neg),
            ("<", lower_pos, negatives - lower_neg),
        ):
            score = tp * negatives + tn * positives
            if score > best_score:
                best_score, best = score, (direction, threshold)
        lower_pos += positive
        lower_neg += negative
    assert best is not None
    return best


def rate(numerator: int, denominator: int) -> dict:
    if not denominator:
        return {
            "numerator": numerator,
            "denominator": 0,
            "value": None,
            "ci95_lower": None,
            "ci95_upper": None,
        }
    value = numerator / denominator
    z = 1.959963984540054
    scale = 1 + z * z / denominator
    center = (value + z * z / (2 * denominator)) / scale
    radius = (
        z
        * math.sqrt(value * (1 - value) / denominator + z * z / (4 * denominator * denominator))
        / scale
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "ci95_lower": 0.0 if numerator == 0 else max(0.0, center - radius),
        "ci95_upper": 1.0 if numerator == denominator else min(1.0, center + radius),
    }


def measure(rows: list[dict], stump: tuple[str, float]) -> dict:
    direction, threshold = stump
    tp = fp = tn = fn = 0
    for row in rows:
        predicted = row[FEATURE] >= threshold if direction == ">=" else row[FEATURE] < threshold
        actual = row["tweet_label"] == 1
        tp += int(predicted and actual)
        fp += int(predicted and not actual)
        tn += int(not predicted and not actual)
        fn += int(not predicted and actual)
    f1_denominator = 2 * tp + fp + fn
    return {
        "n": len(rows),
        "targeted": tp + fn,
        "controls": tn + fp,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": rate(tp, tp + fp),
        "recall": rate(tp, tp + fn),
        "false_positive_rate": rate(fp, fp + tn),
        "f1": 2 * tp / f1_denominator if f1_denominator else None,
        "abstentions": 0,
        "abstention_rate": rate(0, len(rows)),
    }


def build_report(path: Path) -> dict:
    rows, dataset = load_source(path)
    splits = {key: [] for key in ("train", "validation", "test")}
    for row in rows:
        splits[partition(row["id"])].append(row)
    # Freeze membership first, then fit exactly one predeclared feature on train only.
    membership = {
        key: hashlib.sha256(
            "\n".join(
                sorted(hashlib.sha256(row["id"].encode()).hexdigest() for row in values)
            ).encode()
        ).hexdigest()
        for key, values in splits.items()
    }
    stump = fit_stump(splits["train"])
    summaries = {}
    for feature in SUMMARY_FEATURES:
        summaries[feature] = {}
        for label, name in ((1, "targeted"), (0, "controls")):
            values = [row[feature] for row in rows if row["tweet_label"] == label]
            summaries[feature][name] = {"count": len(values), "median": statistics.median(values)}
    return {
        "schema_version": 1,
        "available": True,
        "scope": "historical_tweet_targeting_research",
        "source": {
            "title": (
                "Coordinated Reply Attacks in Influence Campaigns: Characterization and Detection"
            ),
            "authors": ["Manita Pote (dataset creator)"],
            "doi": "10.5281/zenodo.13896309",
            "url": "https://zenodo.org/records/13896309",
            "license": "CC-BY-4.0",
            "file_sha256": SOURCE_SHA256,
        },
        "dataset": dataset,
        "baseline": {
            "feature": FEATURE,
            "direction": stump[0],
            "threshold": stump[1],
            "selection": "train_only_balanced_accuracy",
        },
        "splits": {key: measure(values, stump) for key, values in splits.items()},
        "reproducibility": {
            "algorithm": "one_feature_decision_stump_v1",
            "python_version": platform.python_version(),
            "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "split_method": (
                "SHA256('bounceri-reply-preview-v1:'+raw_tweet_ID) modulo 100; "
                "train <70; validation 70..84; test >=85"
            ),
            "membership_sha256": membership,
            "deduplication": "first source row per tweet ID; conflicting labels rejected",
            "confidence_intervals": "Wilson 95% for binomial rates only; F1 has no interval",
            "decision_policy": "always decide; zero abstentions; no calibrated probability",
        },
        "feature_summaries": summaries,
        "limitations": [
            (
                "Conditional tweet-level historical benchmark; "
                "not a validated social coordination module."
            ),
            (
                "Label 1 means targeted by historical influence-operation replies "
                "(at least five IO replies), not that the target is a bot or malicious actor."
            ),
            (
                "Controls are selected posts with at least five replies, "
                "not ordinary or independently verified benign traffic."
            ),
            (
                "Actor and campaign group IDs are unavailable; actor/campaign leakage is "
                "unverified. This is not a genuinely hidden test."
            ),
            (
                "Historical heuristic labels do not establish current coordination, "
                "attribution, bot identity or maliciousness."
            ),
            (
                "One predeclared mean_cosine stump is selected on train only; validation/test "
                "are reported separately, with no tuning on them."
            ),
            (
                "Descriptive medians use all deduplicated posts; "
                "they do not select features or thresholds."
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.source)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
