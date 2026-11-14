"""Publish only the reviewed, explicitly synthetic evaluation artifact."""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

REPORT_PATH = Path(__file__).resolve().parents[3] / "models/evaluation.synthetic.json"
router = APIRouter()
Count = Annotated[int, Field(ge=0)]
Probability = Annotated[float, Field(ge=0, le=1)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Statistic(Record):
    numerator: Count
    denominator: Annotated[int, Field(gt=0)]
    value: Probability
    ci95_lower: Probability
    ci95_upper: Probability

    @model_validator(mode="after")
    def consistent(self):
        if (
            self.numerator > self.denominator
            or abs(self.value - self.numerator / self.denominator) > 1e-12
            or self.ci95_lower > self.value + 1e-12
            or self.ci95_upper < self.value - 1e-12
        ):
            raise ValueError("inconsistent statistic")
        return self


class Dataset(Record):
    id: str
    split: Literal["reserved_known_templates"]
    n_known: Count
    n_unknown: Count
    n_sessions: Annotated[int, Field(gt=0)]
    n_runs: Annotated[int, Field(gt=0)]


class Detector(Record):
    model_version: str
    freeze_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    source_code_sha256: dict[str, Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]]


class Metrics(Record):
    bad_bot_precision: Statistic
    human_false_positive_rate: Statistic
    uncertain_share: Statistic


class Evaluation(Record):
    schema_version: Literal[1]
    available: Literal[True]
    synthetic: Literal[True]
    dataset: Dataset
    detector: Detector
    metrics: Metrics
    limitations: Annotated[list[Annotated[str, Field(max_length=500)]], Field(max_length=20)]
    unavailable: list[Literal["independent_real_humans", "genuinely_hidden_attack"]]


@router.get("/api/evaluation")
def evaluation():
    try:
        return Evaluation.model_validate_json(REPORT_PATH.read_text(encoding="utf-8")).model_dump()
    except FileNotFoundError:
        return {"available": False, "synthetic": True, "reason": "Evaluation not published"}
    except (OSError, ValidationError) as exc:
        raise HTTPException(503, "Published evaluation is unavailable") from exc
