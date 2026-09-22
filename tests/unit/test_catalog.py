import json
from decimal import Decimal
from pathlib import Path

import pytest

from packages.evaluation_engine.catalog import (
    CatalogLoadError,
    catalog_quality_issues,
    detect_duplicate_product_ids,
    load_catalog,
    normalize_product_attributes,
    validate_controlled_demo_catalog,
)
from packages.evaluation_engine.models import Product

CATALOG_PATH = Path(__file__).parents[2] / "data" / "demo" / "catalog-v1.json"


def make_product(**updates: object) -> Product:
    values: dict[str, object] = {
        "product_id": "test-1", "title": "Test Shoe", "category": "shoes",
        "subcategory": "running_shoes", "brand": "Test Brand", "gender": "men",
        "color": "black", "sizes": ["8", "9"], "price": Decimal(1000),
        "currency": "INR", "availability": "in_stock",
        "attributes": {"material": "mesh"}, "field_provenance": {"title": "controlled"},
    }
    values.update(updates)
    return Product.model_validate(values)


def test_controlled_catalog_has_exact_contract() -> None:
    catalog = load_catalog(CATALOG_PATH)
    report = validate_controlled_demo_catalog(catalog)
    assert report["product_count"] == 100
    assert report["category_counts"] == {"bags": 10, "clothing": 25, "electronics": 20, "shoes": 35, "watches": 10}
    assert report["invalid_product_count"] == 0
    assert report["duplicate_count"] == 0
    assert report["valid"] is True


def test_catalog_product_ids_are_unique() -> None:
    catalog = load_catalog(CATALOG_PATH)
    assert len({product.product_id for product in catalog.products}) == 100


def test_duplicate_detector_returns_sorted_ids() -> None:
    items = [{"product_id": "p-2"}, {"product_id": "p-1"}, {"product_id": "p-2"}, {"product_id": "p-1"}]
    assert detect_duplicate_product_ids(items) == ["p-1", "p-2"]


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    product = make_product().model_dump(mode="json")
    path = tmp_path / "duplicates.json"
    path.write_text(json.dumps({"catalog_id": "bad", "version": "v1", "products": [product, product]}), encoding="utf-8")
    with pytest.raises(CatalogLoadError, match="Duplicate product IDs"):
        load_catalog(path)


def test_loader_rejects_invalid_product(tmp_path: Path) -> None:
    product = make_product().model_dump(mode="json")
    product["price"] = "-1"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"catalog_id": "bad", "version": "v1", "products": [product]}), encoding="utf-8")
    with pytest.raises(CatalogLoadError, match="schema validation failed"):
        load_catalog(path)


def test_normalizer_applies_known_aliases() -> None:
    product = make_product(category=" Shoes ", gender=" Male ", color=" Gray ", sizes=[" m "])
    normalized = normalize_product_attributes(product)
    assert normalized.category == "shoes"
    assert normalized.gender == "men"
    assert normalized.color == "grey"
    assert normalized.sizes == ["M"]


def test_quality_checker_finds_unknown_values() -> None:
    product = make_product(color="orange", gender="child")
    assert catalog_quality_issues(product) == ["UNKNOWN_COLOR", "UNKNOWN_GENDER"]


def test_quality_checker_finds_missing_structured_attribute() -> None:
    product = make_product(category="electronics", sizes=[], attributes={})
    assert catalog_quality_issues(product) == ["MISSING_ATTRIBUTE:warranty_months"]
