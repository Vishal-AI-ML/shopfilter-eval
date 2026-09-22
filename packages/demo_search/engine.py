from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from packages.evaluation_engine.models import (
    Catalog,
    ParsedIntent,
    Product,
    RankedProductResult,
    SearchConstraints,
    SearchRequest,
    SearchResponse,
)
from packages.evaluation_engine.query_parser import parse_query

CONFIG_PATH = Path(__file__).with_name("search_config.json")
TOKEN_RE = re.compile(r"[a-z0-9]+")


class DemoSearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_version: str = Field(min_length=1)
    candidate_limit: int = Field(ge=1)
    field_weights: dict[str, float]


def load_search_config(path: str | Path = CONFIG_PATH) -> DemoSearchConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return DemoSearchConfig.model_validate(raw)


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return set(TOKEN_RE.findall(value.lower().replace("_", " ")))


def _product_fields(product: Product) -> dict[str, str | None]:
    return {
        "title": product.title,
        "subcategory": product.subcategory,
        "category": product.category,
        "brand": product.brand,
        "description": product.description,
        "color": product.color,
    }


def _score_product(
    product: Product,
    query_tokens: set[str],
    weights: dict[str, float],
) -> tuple[float, dict[str, float]]:
    if not query_tokens:
        return 1.0, {"fallback": 1.0}

    breakdown: dict[str, float] = {}
    for field, value in _product_fields(product).items():
        matches = query_tokens & _tokens(value)
        if matches:
            breakdown[field] = weights.get(field, 0.0) * len(matches) / len(query_tokens)
    return sum(breakdown.values()), breakdown


def _same(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left.casefold() == right.casefold()


def _satisfies_constraints(product: Product, constraints: SearchConstraints) -> bool:
    if constraints.category and not _same(product.category, constraints.category):
        return False
    if constraints.subcategory and not _same(product.subcategory, constraints.subcategory):
        return False
    if constraints.brand and not _same(product.brand, constraints.brand):
        return False
    if constraints.gender and not _same(product.gender, constraints.gender):
        return False
    if constraints.color and not _same(product.color, constraints.color):
        return False
    if constraints.min_price is not None and product.price < constraints.min_price:
        return False
    if constraints.max_price is not None and product.price > constraints.max_price:
        return False
    if constraints.size and constraints.size.casefold() not in {
        size.casefold() for size in product.sizes
    }:
        return False
    return (
        constraints.availability is None
        or product.availability == constraints.availability
    )


class DemoSearchEngine:
    def __init__(self, catalog: Catalog, config: DemoSearchConfig | None = None) -> None:
        self.catalog = catalog
        self.config = config or load_search_config()

    def _retrieve(
        self,
        intent: ParsedIntent,
    ) -> list[tuple[Product, float, dict[str, float]]]:
        query_tokens = _tokens(intent.query_text)
        scored: list[tuple[Product, float, dict[str, float]]] = []
        for product in self.catalog.products:
            score, breakdown = _score_product(
                product,
                query_tokens,
                self.config.field_weights,
            )
            if score > 0:
                scored.append((product, score, breakdown))
        scored.sort(key=lambda item: (-item[1], item[0].product_id))
        return scored[: self.config.candidate_limit]

    def search(self, request: SearchRequest) -> SearchResponse:
        started = perf_counter()
        intent = parse_query(request.query)
        retrieved = self._retrieve(intent)
        filtered = [
            item
            for item in retrieved
            if _satisfies_constraints(item[0], intent.constraints)
        ]
        filtered.sort(key=lambda item: (-item[1], item[0].product_id))
        selected = filtered[: request.top_k]
        ranked = [
            RankedProductResult(
                product=product,
                rank=index,
                score=round(score, 6),
                metadata={"score_breakdown": breakdown},
            )
            for index, (product, score, breakdown) in enumerate(selected, start=1)
        ]
        latency_ms = (perf_counter() - started) * 1000
        return SearchResponse(
            query=request.query,
            interpreted_query=intent,
            applied_filters=intent.constraints,
            retrieved_candidates=[item[0].product_id for item in retrieved],
            filtered_candidates=[item[0].product_id for item in filtered],
            products=ranked,
            latency_ms=latency_ms,
            provider="shopfilter-demo",
            system_version=self.config.system_version,
            metadata={
                "seed": request.seed,
                "candidate_count": len(retrieved),
                "filtered_count": len(filtered),
                "returned_count": len(ranked),
                "pipeline_stages": [
                    "query_understanding",
                    "retrieval",
                    "filtering",
                    "ranking",
                ],
            },
        )
