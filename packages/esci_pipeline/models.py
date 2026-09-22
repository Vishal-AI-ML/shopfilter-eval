
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.evaluation_engine.models import ExpectedProduct


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EsciDraftCase(StrictModel):
    case_id: str = Field(min_length=1)
    query_id: int
    query: str = Field(min_length=1)
    locale: Literal["us"] = "us"
    split: Literal["train", "test"]
    expected_products: list[ExpectedProduct]
    review_status: Literal["IN_REVIEW"] = "IN_REVIEW"
    source_provenance: dict[str, str]


class EsciDraftDataset(StrictModel):
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["IN_REVIEW"] = "IN_REVIEW"
    catalog_id: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    source_manifest_id: str = Field(min_length=1)
    cases: list[EsciDraftCase]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProcessedFileRecord(StrictModel):
    name: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class PreparationReport(StrictModel):
    pipeline_version: str
    source_manifest_id: str
    source_commit: str
    locale: str
    version_flag: str
    requested_product_count: int
    actual_product_count: int
    query_count: int
    judgment_count: int
    split_counts: dict[str, int]
    label_counts: dict[str, int]
    missing_title_count: int
    synthetic_fields: list[str]
    output_files: list[ProcessedFileRecord]
    selection: dict[str, Any]
