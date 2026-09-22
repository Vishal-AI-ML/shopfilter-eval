from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from packages.evaluation_engine.models import Catalog, Product

DEMO_CATEGORY_TARGETS = {"shoes": 35, "clothing": 25, "electronics": 20, "bags": 10, "watches": 10}
ALLOWED_COLORS = {"beige", "black", "blue", "brown", "green", "grey", "navy", "pink", "purple", "red", "silver", "tan", "white"}
ALLOWED_GENDERS = {"men", "women", "unisex"}
COLOR_ALIASES = {"gray": "grey"}
GENDER_ALIASES = {"male": "men", "men's": "men", "female": "women", "women's": "women"}
REQUIRED_ATTRIBUTES = {"electronics": {"warranty_months"}, "bags": {"capacity_liters"}, "watches": {"strap_material"}}


class CatalogLoadError(ValueError):
    """Raised when a catalog file cannot be parsed or validated."""


class CatalogValidationError(ValueError):
    """Raised when the controlled demo catalog violates its contract."""


def detect_duplicate_product_ids(items: Iterable[Mapping[str, Any] | Product]) -> list[str]:
    product_ids: list[str] = []
    for item in items:
        if isinstance(item, Product):
            product_ids.append(item.product_id)
        else:
            value = item.get("product_id")
            if isinstance(value, str):
                product_ids.append(value)
    counts = Counter(product_ids)
    return sorted(product_id for product_id, count in counts.items() if count > 1)


def load_catalog(path: str | Path) -> Catalog:
    catalog_path = Path(path)
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogLoadError(f"Unable to read catalog: {catalog_path}") from exc
    if not isinstance(raw, dict):
        raise CatalogLoadError("Catalog root must be a JSON object")
    raw_products = raw.get("products")
    if not isinstance(raw_products, list):
        raise CatalogLoadError("Catalog products must be a JSON array")
    duplicates = detect_duplicate_product_ids(item for item in raw_products if isinstance(item, dict))
    if duplicates:
        raise CatalogLoadError(f"Duplicate product IDs: {', '.join(duplicates)}")
    try:
        return Catalog.model_validate(raw)
    except ValidationError as exc:
        raise CatalogLoadError("Catalog schema validation failed") from exc


def normalize_product_attributes(product: Product) -> Product:
    color = product.color.strip().lower() if product.color else None
    gender = product.gender.strip().lower() if product.gender else None
    if color:
        color = COLOR_ALIASES.get(color, color)
    if gender:
        gender = GENDER_ALIASES.get(gender, gender)
    return product.model_copy(update={
        "category": product.category.strip().lower(),
        "subcategory": product.subcategory.strip().lower() if product.subcategory else None,
        "brand": product.brand.strip() if product.brand else None,
        "gender": gender,
        "color": color,
        "sizes": [size.strip().upper() for size in product.sizes],
    })


def catalog_quality_issues(product: Product) -> list[str]:
    issues: list[str] = []
    if product.color is not None and product.color not in ALLOWED_COLORS:
        issues.append("UNKNOWN_COLOR")
    if product.gender is not None and product.gender not in ALLOWED_GENDERS:
        issues.append("UNKNOWN_GENDER")
    if product.category in {"shoes", "clothing"} and not product.sizes:
        issues.append("MISSING_SIZES")
    for attribute in REQUIRED_ATTRIBUTES.get(product.category, set()):
        value = product.attributes.get(attribute)
        if value is None or value == "":
            issues.append(f"MISSING_ATTRIBUTE:{attribute}")
    if not product.field_provenance:
        issues.append("MISSING_FIELD_PROVENANCE")
    return issues


def catalog_report(catalog: Catalog) -> dict[str, Any]:
    category_counts = dict(sorted(Counter(p.category for p in catalog.products).items()))
    product_issues = {p.product_id: issues for p in catalog.products if (issues := catalog_quality_issues(p))}
    duplicates = detect_duplicate_product_ids(catalog.products)
    return {"catalog_id": catalog.catalog_id, "version": catalog.version, "product_count": len(catalog.products), "category_counts": category_counts, "duplicate_ids": duplicates, "duplicate_count": len(duplicates), "product_issues": product_issues, "invalid_product_count": len(product_issues), "valid": not duplicates and not product_issues}


def validate_controlled_demo_catalog(catalog: Catalog) -> dict[str, Any]:
    report = catalog_report(catalog)
    errors: list[str] = []
    if report["product_count"] != 100:
        errors.append(f"Expected 100 products, found {report['product_count']}")
    if report["category_counts"] != DEMO_CATEGORY_TARGETS:
        errors.append("Category distribution does not match the controlled catalog contract")
    if report["duplicate_count"]:
        errors.append("Duplicate product IDs found")
    if report["invalid_product_count"]:
        errors.append("Catalog quality issues found")
    if errors:
        raise CatalogValidationError("; ".join(errors))
    return report
