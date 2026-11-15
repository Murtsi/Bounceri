"""Serve only a bounded, strictly typed aggregate historical research report."""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, ValidationError, model_validator

from bouncer.api.evaluation import Count, Probability, Record

REPORT_PATH = Path(__file__).resolve().parents[3] / "models/evaluation.social_replies.json"
MAX_REPORT_BYTES = 64 * 1024
router = APIRouter()
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Text = Annotated[str, Field(max_length=600)]


class Rate(Record):
    numerator: Count
    denominator: Count
    value: Probability | None
    ci95_lower: Probability | None
    ci95_upper: Probability | None

    @model_validator(mode="after")
    def consistent(self):
        if self.numerator > self.denominator:
            raise ValueError("invalid counts")
        if not self.denominator:
            if any(v is not None for v in (self.value, self.ci95_lower, self.ci95_upper)):
                raise ValueError("undefined rate")
        elif (
            self.value is None
            or self.ci95_lower is None
            or self.ci95_upper is None
            or abs(self.value - self.numerator / self.denominator) > 1e-12
            or self.ci95_lower > self.value + 1e-12
            or self.ci95_upper < self.value - 1e-12
        ):
            raise ValueError("inconsistent rate")
        return self


class Confusion(Record):
    tp: Count
    fp: Count
    tn: Count
    fn: Count


class Split(Record):
    n: Annotated[int, Field(gt=0)]
    targeted: Count
    controls: Count
    confusion: Confusion
    precision: Rate
    recall: Rate
    false_positive_rate: Rate
    f1: Probability | None
    abstentions: Literal[0]
    abstention_rate: Rate

    @model_validator(mode="after")
    def consistent(self):
        c = self.confusion
        expected = (
            (self.precision, c.tp, c.tp + c.fp),
            (self.recall, c.tp, c.tp + c.fn),
            (self.false_positive_rate, c.fp, c.fp + c.tn),
            (self.abstention_rate, 0, self.n),
        )
        if (
            self.n != self.targeted + self.controls
            or self.targeted != c.tp + c.fn
            or self.controls != c.tn + c.fp
            or any(r.numerator != num or r.denominator != den for r, num, den in expected)
        ):
            raise ValueError("inconsistent split counts")
        denominator = 2 * c.tp + c.fp + c.fn
        if denominator and (self.f1 is None or abs(self.f1 - 2 * c.tp / denominator) > 1e-12):
            raise ValueError("inconsistent F1")
        if not denominator and self.f1 is not None:
            raise ValueError("undefined F1")
        return self


class Splits(Record):
    train: Split
    validation: Split
    test: Split


class Source(Record):
    title: Text
    authors: Annotated[list[Text], Field(min_length=1, max_length=10)]
    doi: Literal["10.5281/zenodo.13896309"]
    url: Literal["https://zenodo.org/records/13896309"]
    license: Literal["CC-BY-4.0"]
    file_sha256: Literal["038783083dfad6f8b80949a352044b9eacb65ad1e1cdbbfaebb20e9fd501533f"]


class Dataset(Record):
    raw_rows: Annotated[int, Field(gt=0)]
    unique_posts: Annotated[int, Field(gt=0)]
    targeted: Count
    controls: Count
    duplicate_id_rows: Count
    numeric_features: Literal[99]


class Baseline(Record):
    feature: Literal["mean_cosine"]
    direction: Literal[">=", "<"]
    threshold: Annotated[float, Field(allow_inf_nan=False)]
    selection: Literal["train_only_balanced_accuracy"]


class Membership(Record):
    train: Digest
    validation: Digest
    test: Digest


class Reproducibility(Record):
    algorithm: Literal["one_feature_decision_stump_v1"]
    python_version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    evaluator_sha256: Digest
    split_method: Text
    membership_sha256: Membership
    deduplication: Text
    confidence_intervals: Text
    decision_policy: Text


class Summary(Record):
    count: Count
    median: Annotated[float, Field(allow_inf_nan=False)]


class ByLabel(Record):
    targeted: Summary
    controls: Summary


class FeatureSummaries(Record):
    mean_cosine: ByLabel
    median_diff_min: ByLabel = Field(alias="50%_diff_min")
    org_reply_count: ByLabel


class SocialPreview(Record):
    schema_version: Literal[1]
    available: Literal[True]
    scope: Literal["historical_tweet_targeting_research"]
    source: Source
    dataset: Dataset
    baseline: Baseline
    splits: Splits
    reproducibility: Reproducibility
    feature_summaries: FeatureSummaries
    limitations: Annotated[list[Text], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def consistent(self):
        d = self.dataset
        splits = (self.splits.train, self.splits.validation, self.splits.test)
        if (
            d.raw_rows != d.unique_posts + d.duplicate_id_rows
            or d.unique_posts != d.targeted + d.controls
            or sum(s.n for s in splits) != d.unique_posts
            or sum(s.targeted for s in splits) != d.targeted
            or sum(s.controls for s in splits) != d.controls
        ):
            raise ValueError("inconsistent dataset counts")
        return self


@router.get("/api/evaluation/social-replies")
def social_replies():
    try:
        with REPORT_PATH.open("rb") as handle:
            data = handle.read(MAX_REPORT_BYTES + 1)
        if len(data) > MAX_REPORT_BYTES:
            raise ValueError("report too large")
        return SocialPreview.model_validate_json(data).model_dump(by_alias=True)
    except (OSError, ValueError, ValidationError) as exc:
        raise HTTPException(503, "Historical reply research preview is unavailable") from exc
