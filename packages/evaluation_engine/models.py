from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class RelevanceLabel(StrEnum):
    EXACT = "E"
    SUBSTITUTE = "S"
    COMPLEMENT = "C"
    IRRELEVANT = "I"


class MetricType(StrEnum):
    DETERMINISTIC = "deterministic"
    JUDGMENT = "judgment"
    OPERATIONAL = "operational"


class EvidenceStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class FailureType(StrEnum):
    QUERY_UNDERSTANDING = "QUERY_UNDERSTANDING"
    FILTER_EXTRACTION = "FILTER_EXTRACTION"
    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    RETRIEVAL_NOISE = "RETRIEVAL_NOISE"
    FILTER_VIOLATION = "FILTER_VIOLATION"
    RANKING_FAILURE = "RANKING_FAILURE"
    SEMANTIC_RELEVANCE_FAILURE = "SEMANTIC_RELEVANCE_FAILURE"
    CATALOG_DATA_QUALITY = "CATALOG_DATA_QUALITY"
    LATENCY_FAILURE = "LATENCY_FAILURE"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    UNKNOWN = "UNKNOWN"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Product(StrictModel):
    product_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    category: str = Field(min_length=1)
    subcategory: str | None = None
    brand: str | None = None
    gender: str | None = None
    color: str | None = None
    sizes: list[str] = Field(default_factory=list)
    price: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    availability: Availability = Availability.UNKNOWN
    rating: float | None = Field(default=None, ge=0, le=5)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    field_provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("product_id", "title", "category")
    @classmethod
    def reject_blank_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value


class Catalog(StrictModel):
    catalog_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    products: list[Product]

    @model_validator(mode="after")
    def reject_duplicate_product_ids(self) -> Catalog:
        ids = [product.product_id for product in self.products]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate product IDs are not allowed")
        return self


class SearchConstraints(StrictModel):
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    gender: str | None = None
    color: str | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    size: str | None = None
    availability: Availability | None = None

    @model_validator(mode="after")
    def validate_price_range(self) -> SearchConstraints:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")
        return self


class ParsedIntent(StrictModel):
    query_text: str
    constraints: SearchConstraints = Field(default_factory=SearchConstraints)
    sorting_intent: str | None = None
    unknown_terms: list[str] = Field(default_factory=list)


class SearchRequest(StrictModel):
    query: str
    top_k: int = Field(default=10, ge=1)
    seed: int = 0

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class RankedProductResult(StrictModel):
    product: Product
    rank: int = Field(ge=1)
    score: float = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(StrictModel):
    query: str
    interpreted_query: ParsedIntent | None = None
    applied_filters: SearchConstraints | None = None
    retrieved_candidates: list[str] | None = None
    filtered_candidates: list[str] | None = None
    products: list[RankedProductResult] = Field(default_factory=list)
    latency_ms: float = Field(ge=0)
    provider: str = Field(min_length=1)
    system_version: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExpectedProduct(StrictModel):
    product_id: str = Field(min_length=1)
    relevance: RelevanceLabel
    expected_rank: int | None = Field(default=None, ge=1)


class EvaluationCase(StrictModel):
    case_id: str = Field(min_length=1)
    query: str
    expected_intent: ParsedIntent | None = None
    expected_constraints: SearchConstraints = Field(default_factory=SearchConstraints)
    expected_products: list[ExpectedProduct] = Field(default_factory=list)
    difficulty: str = "normal"
    source: str = "manual"
    reviewed: bool = False

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class MetricEvidence(StrictModel):
    status: EvidenceStatus = EvidenceStatus.AVAILABLE
    observed: dict[str, Any] = Field(default_factory=dict)
    explanation: str | None = None


class MetricResult(StrictModel):
    metric_name: str = Field(min_length=1)
    metric_type: MetricType
    value: float | None = None
    passed: bool | None = None
    evidence: MetricEvidence
    explanation: str | None = None


class FailureEvidence(StrictModel):
    observed_facts: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    recommended_investigation: list[str] = Field(default_factory=list)
    recommended_fix: list[str] = Field(default_factory=list)


class Failure(StrictModel):
    failure_type: FailureType
    severity: str
    component: str
    confidence: float = Field(ge=0, le=1)
    evidence: FailureEvidence
    status: str = "open"
    notes: str | None = None


class EvaluationRunMetadata(StrictModel):
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    search_system_version: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    metric_definition_version: str = Field(min_length=1)
    judge_config: dict[str, Any] | None = None
    git_sha: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
