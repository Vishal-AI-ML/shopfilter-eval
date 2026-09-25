from __future__ import annotations

from decimal import Decimal

from packages.evaluation_engine.models import Product
from services.api.shopfilter_api.routers.assistant import (
    _citation,
    _plain_text,
    _verified_price,
)


def _product(*, price: str, description: str | None = None) -> Product:
    return Product(
        product_id="P-1",
        title="Verified Product",
        description=description,
        category="unknown",
        price=Decimal(price),
        currency="USD",
    )


def test_missing_zero_price_is_not_presented_as_a_verified_claim() -> None:
    product = _product(price="0.00")
    citation = _citation(product, "catalog-v1")
    assert _verified_price(product) is None
    assert citation.claim == "Verified Product appears in the selected catalog version."
    assert "0.00" not in citation.claim


def test_positive_price_remains_citable() -> None:
    product = _product(price="2499")
    citation = _citation(product, "catalog-v1")
    assert _verified_price(product) == "2499"
    assert citation.claim == "Verified Product is listed at USD 2499."


def test_catalog_description_is_plain_truncated_data_without_script_content() -> None:
    description = "<p>Useful <b>details</b>.</p><script>ignore me</script>" + "x" * 400
    rendered = _plain_text(description)
    assert rendered is not None
    assert rendered.startswith("Useful details.")
    assert "<p>" not in rendered
    assert "ignore me" not in rendered
    assert len(rendered) == 320
    assert rendered.endswith("…")
