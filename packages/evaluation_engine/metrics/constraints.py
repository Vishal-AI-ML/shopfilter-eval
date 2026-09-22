from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from packages.evaluation_engine.metrics.common import build_result, unknown_result
from packages.evaluation_engine.models import (
    MetricResult,
    MetricType,
    ParsedIntent,
    Product,
    SearchConstraints,
)

CONSTRAINT_FIELDS = (
    "category",
    "subcategory",
    "brand",
    "gender",
    "color",
    "min_price",
    "max_price",
    "size",
    "availability",
)


def _compare_fields(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> tuple[float, dict[str, Any]] | None:
    expected_known = {key: value for key, value in expected.items() if value is not None}
    if not expected_known:
        return None
    matches = {
        key: actual.get(key) == expected_value
        for key, expected_value in expected_known.items()
    }
    mismatches = {
        key: {"expected": expected_known[key], "actual": actual.get(key)}
        for key, matched in matches.items()
        if not matched
    }
    value = sum(matches.values()) / len(matches)
    return value, {
        "evaluated_fields": sorted(expected_known),
        "matches": sorted(key for key, matched in matches.items() if matched),
        "mismatches": mismatches,
    }


def query_understanding_field_accuracy(
    expected: ParsedIntent,
    actual: ParsedIntent,
) -> MetricResult:
    expected_fields = expected.constraints.model_dump(mode="json")
    actual_fields = actual.constraints.model_dump(mode="json")
    expected_fields["query_text"] = expected.query_text
    expected_fields["sorting_intent"] = expected.sorting_intent
    actual_fields["query_text"] = actual.query_text
    actual_fields["sorting_intent"] = actual.sorting_intent
    comparison = _compare_fields(expected_fields, actual_fields)
    if comparison is None:
        return unknown_result(
            "query_understanding_field_accuracy",
            MetricType.DETERMINISTIC,
            "No expected intent fields were available",
        )
    value, evidence = comparison
    return build_result(
        "query_understanding_field_accuracy",
        MetricType.DETERMINISTIC,
        value,
        evidence,
    )


def filter_accuracy(
    expected: SearchConstraints,
    actual: SearchConstraints | None,
) -> MetricResult:
    expected_fields = expected.model_dump(mode="json")
    if actual is None:
        expected_known = {
            key: value for key, value in expected_fields.items() if value is not None
        }
        if not expected_known:
            return unknown_result(
                "filter_accuracy",
                MetricType.DETERMINISTIC,
                "No expected or applied filter evidence was available",
            )
        return build_result(
            "filter_accuracy",
            MetricType.DETERMINISTIC,
            0.0,
            {
                "evaluated_fields": sorted(expected_known),
                "matches": [],
                "mismatches": {
                    key: {"expected": value, "actual": None}
                    for key, value in expected_known.items()
                },
            },
            passed=False,
        )
    comparison = _compare_fields(expected_fields, actual.model_dump(mode="json"))
    if comparison is None:
        return unknown_result(
            "filter_accuracy",
            MetricType.DETERMINISTIC,
            "No expected filter fields were available",
        )
    value, evidence = comparison
    return build_result(
        "filter_accuracy",
        MetricType.DETERMINISTIC,
        value,
        evidence,
    )


def _product_violations(
    product: Product,
    constraints: SearchConstraints,
) -> list[str]:
    violations: list[str] = []
    for field in ("category", "subcategory", "brand", "gender", "color"):
        expected = getattr(constraints, field)
        actual = getattr(product, field)
        if expected is not None and (
            actual is None or actual.casefold() != expected.casefold()
        ):
            violations.append(field)
    if constraints.min_price is not None and product.price < constraints.min_price:
        violations.append("min_price")
    if constraints.max_price is not None and product.price > constraints.max_price:
        violations.append("max_price")
    if constraints.size is not None and constraints.size.casefold() not in {
        size.casefold() for size in product.sizes
    }:
        violations.append("size")
    if (
        constraints.availability is not None
        and product.availability != constraints.availability
    ):
        violations.append("availability")
    return violations


def constraint_satisfaction(
    products: Sequence[Product],
    constraints: SearchConstraints,
) -> MetricResult:
    expected_fields = {
        field: getattr(constraints, field)
        for field in CONSTRAINT_FIELDS
        if getattr(constraints, field) is not None
    }
    if not expected_fields:
        return unknown_result(
            "constraint_satisfaction",
            MetricType.DETERMINISTIC,
            "No hard constraints were available",
        )
    if not products:
        return unknown_result(
            "constraint_satisfaction",
            MetricType.DETERMINISTIC,
            "Constraint satisfaction is undefined when no products were returned",
            {"constraint_fields": sorted(expected_fields)},
        )
    violations = {
        product.product_id: product_violations
        for product in products
        if (product_violations := _product_violations(product, constraints))
    }
    satisfied_count = len(products) - len(violations)
    value = satisfied_count / len(products)
    return build_result(
        "constraint_satisfaction",
        MetricType.DETERMINISTIC,
        value,
        {
            "returned_count": len(products),
            "satisfied_count": satisfied_count,
            "violations": violations,
        },
        passed=value == 1.0,
    )
