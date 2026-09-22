from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from packages.evaluation_engine.models import (
    Catalog,
    RankedProductResult,
    SearchConstraints,
    SearchRequest,
    SearchResponse,
)
from packages.search_adapters.base import AdapterCapabilities, SearchAdapter

PROFILES_PATH = (
    Path(__file__).parents[1] / "demo_search" / "failure_profiles.json"
)


class FailureMode(StrEnum):
    HEALTHY = "healthy"
    FILTER_BROKEN = "filter_broken"
    RETRIEVAL_BROKEN = "retrieval_broken"
    RANKING_BROKEN = "ranking_broken"
    QUERY_PARSER_REGRESSION = "query_parser_regression"
    LATENCY_REGRESSION = "latency_regression"


class FailureProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1)
    mode: FailureMode
    system_version: str = Field(min_length=1)
    latency_injection_ms: float = Field(ge=0)


def load_failure_profiles(
    path: str | Path = PROFILES_PATH,
) -> dict[str, FailureProfile]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        profile_id: FailureProfile.model_validate(profile)
        for profile_id, profile in raw.items()
    }


def _rerank(products: list[RankedProductResult]) -> list[RankedProductResult]:
    return [
        product.model_copy(update={"rank": rank})
        for rank, product in enumerate(products, start=1)
    ]


def _drop_constraint(constraints: SearchConstraints) -> SearchConstraints:
    for field in (
        "brand",
        "color",
        "gender",
        "size",
        "max_price",
        "category",
        "subcategory",
    ):
        if getattr(constraints, field) is not None:
            return constraints.model_copy(update={field: None})
    return constraints


class FaultInjectingSearchAdapter:
    def __init__(
        self,
        base_adapter: SearchAdapter,
        catalog: Catalog,
        profile: FailureProfile,
    ) -> None:
        self._base_adapter = base_adapter
        self._catalog_by_id = {
            product.product_id: product for product in catalog.products
        }
        self.profile = profile

    @property
    def provider_name(self) -> str:
        return self._base_adapter.provider_name

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._base_adapter.capabilities

    async def search(self, request: SearchRequest) -> SearchResponse:
        response = await self._base_adapter.search(request)
        response = response.model_copy(
            update={
                "system_version": self.profile.system_version,
                "metadata": {
                    **response.metadata,
                    "failure_profile": self.profile.profile_id,
                    "failure_mode": self.profile.mode.value,
                },
            }
        )
        if self.profile.mode == FailureMode.HEALTHY:
            return response
        if self.profile.mode == FailureMode.FILTER_BROKEN:
            return self._inject_filter_violation(response)
        if self.profile.mode == FailureMode.RETRIEVAL_BROKEN:
            return self._inject_retrieval_miss(response)
        if self.profile.mode == FailureMode.RANKING_BROKEN:
            return self._inject_ranking_failure(response)
        if self.profile.mode == FailureMode.QUERY_PARSER_REGRESSION:
            return self._inject_parser_regression(response)
        if self.profile.mode == FailureMode.LATENCY_REGRESSION:
            return response.model_copy(
                update={
                    "latency_ms": self.profile.latency_injection_ms
                }
            )
        return response

    def _inject_filter_violation(self, response: SearchResponse) -> SearchResponse:
        filtered_ids = set(response.filtered_candidates or [])
        candidate_id = next(
            (
                product_id
                for product_id in response.retrieved_candidates or []
                if product_id not in filtered_ids
                and product_id in self._catalog_by_id
            ),
            None,
        )
        if candidate_id is None:
            return response
        injected = RankedProductResult(
            product=self._catalog_by_id[candidate_id],
            rank=len(response.products) + 1,
            score=0.000001,
            metadata={"fault_injected": "filter_broken"},
        )
        return response.model_copy(update={"products": [*response.products, injected]})

    def _inject_retrieval_miss(self, response: SearchResponse) -> SearchResponse:
        target_id = (
            response.products[0].product.product_id
            if response.products
            else next(iter(response.retrieved_candidates or []), None)
        )
        if target_id is None:
            return response
        products = [
            product
            for product in response.products
            if product.product.product_id != target_id
        ]
        return response.model_copy(
            update={
                "retrieved_candidates": [
                    product_id
                    for product_id in response.retrieved_candidates or []
                    if product_id != target_id
                ],
                "filtered_candidates": [
                    product_id
                    for product_id in response.filtered_candidates or []
                    if product_id != target_id
                ],
                "products": _rerank(products),
            }
        )

    def _inject_ranking_failure(self, response: SearchResponse) -> SearchResponse:
        if len(response.products) < 2:
            return response
        reordered = [*response.products[1:], response.products[0]]
        return response.model_copy(update={"products": _rerank(reordered)})

    def _inject_parser_regression(self, response: SearchResponse) -> SearchResponse:
        interpreted = response.interpreted_query
        applied = response.applied_filters
        if interpreted is not None:
            interpreted = interpreted.model_copy(
                update={"constraints": _drop_constraint(interpreted.constraints)}
            )
        if applied is not None:
            applied = _drop_constraint(applied)
        return response.model_copy(
            update={
                "interpreted_query": interpreted,
                "applied_filters": applied,
            }
        )
