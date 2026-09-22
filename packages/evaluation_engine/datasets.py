from __future__ import annotations

import hashlib
import json
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from packages.evaluation_engine.models import (
    Catalog,
    ExpectedProduct,
    SearchConstraints,
)


class GoldenDatasetError(ValueError):
    """Raised when a golden dataset cannot be loaded or validated."""


class CaseType(StrEnum):
    FILTER = "filter"
    RETRIEVAL = "retrieval"
    RANKING = "ranking"
    QUERY_UNDERSTANDING = "query_understanding"
    CATALOG_QUALITY = "catalog_quality"


class ReviewStatus(StrEnum):
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"


EXPECTED_DISTRIBUTION = {
    CaseType.FILTER: 8,
    CaseType.RETRIEVAL: 4,
    CaseType.RANKING: 4,
    CaseType.QUERY_UNDERSTANDING: 2,
    CaseType.CATALOG_QUALITY: 2,
}


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    case_type: CaseType
    query: str = Field(min_length=1)
    expected_query_text: str
    expected_constraints: SearchConstraints
    expected_sorting_intent: str | None = None
    expected_products: list[ExpectedProduct] = Field(default_factory=list)
    difficulty: str
    source: str
    review_status: ReviewStatus
    notes: str | None = None

    @field_validator("case_id", "query", "difficulty", "source")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class GoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    catalog_id: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    status: ReviewStatus
    cases: list[GoldenCase]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def compute_dataset_hash(dataset: GoldenDataset) -> str:
    payload = dataset.model_dump(mode="json", exclude={"content_hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_golden_dataset(path: str | Path) -> GoldenDataset:
    dataset_path = Path(path)
    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldenDatasetError(f"Unable to read golden dataset: {dataset_path}") from exc
    try:
        return GoldenDataset.model_validate(raw)
    except ValidationError as exc:
        raise GoldenDatasetError("Golden dataset schema validation failed") from exc


def validate_golden_dataset(
    dataset: GoldenDataset,
    catalog: Catalog,
    *,
    require_approved: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    case_ids = [case.case_id for case in dataset.cases]
    duplicate_case_ids = sorted(
        case_id for case_id, count in Counter(case_ids).items() if count > 1
    )
    if duplicate_case_ids:
        errors.append(f"Duplicate case IDs: {', '.join(duplicate_case_ids)}")

    distribution = Counter(case.case_type for case in dataset.cases)
    if dict(distribution) != EXPECTED_DISTRIBUTION:
        errors.append("Case distribution does not match the Golden V1 prototype contract")

    catalog_product_ids = {product.product_id for product in catalog.products}
    missing_product_ids = sorted(
        {
            expected.product_id
            for case in dataset.cases
            for expected in case.expected_products
            if expected.product_id not in catalog_product_ids
        }
    )
    if missing_product_ids:
        errors.append(f"Unknown expected product IDs: {', '.join(missing_product_ids)}")

    hash_valid = compute_dataset_hash(dataset) == dataset.content_hash
    if not hash_valid:
        errors.append("Dataset content hash does not match its contents")

    approved_cases = sum(
        case.review_status == ReviewStatus.APPROVED for case in dataset.cases
    )
    all_approved = (
        dataset.status == ReviewStatus.APPROVED
        and approved_cases == len(dataset.cases)
    )
    if require_approved and not all_approved:
        errors.append("Dataset is not fully human-approved")

    if errors:
        raise GoldenDatasetError("; ".join(errors))

    return {
        "dataset_id": dataset.dataset_id,
        "version": dataset.version,
        "case_count": len(dataset.cases),
        "distribution": {case_type.value: count for case_type, count in distribution.items()},
        "duplicate_case_ids": duplicate_case_ids,
        "missing_product_ids": missing_product_ids,
        "approved_cases": approved_cases,
        "all_approved": all_approved,
        "hash_valid": hash_valid,
        "content_hash": dataset.content_hash,
    }
