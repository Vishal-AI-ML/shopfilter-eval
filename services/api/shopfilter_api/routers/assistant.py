from __future__ import annotations

import re
import uuid
from html.parser import HTMLParser
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.demo_search.engine import (
    DemoSearchConfig,
    DemoSearchEngine,
    load_search_config,
)
from packages.evaluation_engine.models import Catalog, Product, SearchRequest
from packages.search_adapters.demo import DemoSearchAdapter
from services.api.shopfilter_api.assistant_schemas import (
    AssistantCatalogSummary,
    AssistantCitation,
    AssistantPlaygroundRequest,
    AssistantPlaygroundResponse,
    AssistantProductEvidence,
    AssistantSystemSummary,
)
from services.api.shopfilter_api.dependencies import get_organization_id, get_session
from services.api.shopfilter_api.models import (
    CatalogRecord,
    CatalogVersionRecord,
    ProductRecord,
    SearchSystemRecord,
    SearchSystemVersionRecord,
)

router = APIRouter(prefix="/v1", tags=["assistant playground"])
TenantId = Annotated[uuid.UUID, Depends(get_organization_id)]
DbSession = Annotated[Session, Depends(get_session)]


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def _plain_text(value: str | None, limit: int = 320) -> str | None:
    if not value:
        return None
    parser = _PlainTextParser()
    parser.feed(value)
    normalized = " ".join(" ".join(parser.parts).split())
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    if not normalized:
        return None
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1].rstrip()}…"


def _verified_price(product: Product) -> str | None:
    return format(product.price, "f") if product.price > 0 else None


def _citation(product: Product, source_version: str) -> AssistantCitation:
    price = _verified_price(product)
    claim = (
        f"{product.title} is listed at {product.currency} {price}."
        if price is not None
        else f"{product.title} appears in the selected catalog version."
    )
    return AssistantCitation(
        claim=claim,
        source_id=product.product_id,
        source_version=source_version,
    )


def _catalog_scope(
    session: Session,
    organization_id: uuid.UUID,
    body: AssistantPlaygroundRequest,
) -> tuple[CatalogRecord, CatalogVersionRecord]:
    row = session.execute(
        select(CatalogRecord, CatalogVersionRecord)
        .join(CatalogVersionRecord, CatalogVersionRecord.catalog_id == CatalogRecord.id)
        .where(
            CatalogRecord.organization_id == organization_id,
            CatalogRecord.project_id == body.project_id,
            CatalogVersionRecord.organization_id == organization_id,
            CatalogVersionRecord.id == body.catalog_version_id,
            CatalogVersionRecord.status == "PUBLISHED",
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Published catalog version not found")
    return row[0], row[1]


def _system_scope(
    session: Session,
    organization_id: uuid.UUID,
    body: AssistantPlaygroundRequest,
) -> tuple[SearchSystemRecord, SearchSystemVersionRecord]:
    row = session.execute(
        select(SearchSystemRecord, SearchSystemVersionRecord)
        .join(
            SearchSystemVersionRecord,
            SearchSystemVersionRecord.search_system_id == SearchSystemRecord.id,
        )
        .where(
            SearchSystemRecord.organization_id == organization_id,
            SearchSystemRecord.project_id == body.project_id,
            SearchSystemRecord.status == "ACTIVE",
            SearchSystemVersionRecord.organization_id == organization_id,
            SearchSystemVersionRecord.id == body.ai_system_version_id,
            SearchSystemVersionRecord.status == "PUBLISHED",
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Published AI system version not found")
    return row[0], row[1]


def _answer(products: list[AssistantProductEvidence]) -> tuple[str, list[str]]:
    if not products:
        return (
            (
                "I could not find a catalog product that satisfies the verified constraints. "
                "Try broadening the request or choose another published catalog version."
            ),
            ["No matching product evidence was retrieved."],
        )
    summaries = [
        (
            f"{product.title} ({product.currency} {product.price}) [{product.product_id}]"
            if product.price is not None
            else f"{product.title} [{product.product_id}]"
        )
        for product in products[:3]
    ]
    return (
        (
            f"I found {len(products)} verified catalog "
            f"{'match' if len(products) == 1 else 'matches'}. "
            f"Top evidence-backed options: {'; '.join(summaries)}."
        ),
        [],
    )


@router.post("/assistant/playground", response_model=AssistantPlaygroundResponse)
async def run_assistant_playground(
    body: AssistantPlaygroundRequest,
    organization_id: TenantId,
    session: DbSession,
) -> AssistantPlaygroundResponse:
    catalog_record, catalog_version = _catalog_scope(session, organization_id, body)
    system_record, system_version = _system_scope(session, organization_id, body)
    product_rows = session.scalars(
        select(ProductRecord)
        .where(
            ProductRecord.organization_id == organization_id,
            ProductRecord.catalog_version_id == catalog_version.id,
        )
        .order_by(ProductRecord.product_id)
    ).all()
    products = [Product.model_validate(record.payload) for record in product_rows]
    catalog = Catalog(
        catalog_id=catalog_record.external_id or str(catalog_record.id),
        version=catalog_version.version,
        products=products,
    )
    default_config = load_search_config()
    config = DemoSearchConfig(
        system_version=system_version.version,
        candidate_limit=default_config.candidate_limit,
        field_weights=default_config.field_weights,
    )
    response = await DemoSearchAdapter(DemoSearchEngine(catalog, config)).search(
        SearchRequest(query=body.query, top_k=body.top_k)
    )

    evidence: list[AssistantProductEvidence] = []
    citations: list[AssistantCitation] = []
    for result in response.products:
        product = result.product
        citation = _citation(product, catalog_version.version)
        price = _verified_price(product)
        citations.append(citation)
        breakdown = result.metadata.get("score_breakdown", {})
        evidence.append(
            AssistantProductEvidence(
                product_id=product.product_id,
                title=product.title,
                description=_plain_text(product.description),
                category=product.category,
                brand=product.brand,
                color=product.color,
                price=price,
                currency=product.currency,
                availability=product.availability.value,
                rank=result.rank,
                score=result.score,
                score_breakdown={str(key): float(value) for key, value in breakdown.items()},
                citation=citation,
            )
        )
    answer, missing_information = _answer(evidence)
    return AssistantPlaygroundResponse(
        answer=answer,
        mode="DETERMINISTIC_REFERENCE",
        generation_provider="DISABLED",
        system=AssistantSystemSummary(
            id=system_record.id,
            version_id=system_version.id,
            name=system_record.name,
            version=system_version.version,
            system_type=system_record.system_type,
            provider=system_record.provider,
            capabilities=system_version.capabilities,
            content_hash=system_version.content_hash,
        ),
        catalog=AssistantCatalogSummary(
            id=catalog_record.id,
            version_id=catalog_version.id,
            name=catalog_record.name,
            external_id=catalog_record.external_id,
            version=catalog_version.version,
            content_hash=catalog_version.content_hash,
        ),
        interpreted_query=(
            response.interpreted_query.model_dump(mode="json")
            if response.interpreted_query
            else None
        ),
        applied_filters=(
            response.applied_filters.model_dump(mode="json")
            if response.applied_filters
            else None
        ),
        retrieved_candidate_ids=response.retrieved_candidates or [],
        filtered_candidate_ids=response.filtered_candidates or [],
        products=evidence,
        citations=citations,
        missing_information=missing_information,
        latency_ms=round(response.latency_ms, 3),
    )
