from decimal import Decimal

from packages.evaluation_engine.metrics import (
    constraint_satisfaction,
    filter_accuracy,
    query_understanding_field_accuracy,
)
from packages.evaluation_engine.models import (
    EvidenceStatus,
    ParsedIntent,
    Product,
    SearchConstraints,
)


def make_product(
    product_id: str,
    *,
    color: str,
    price: int,
) -> Product:
    return Product(
        product_id=product_id,
        title=f"{color} running shoe",
        category="shoes",
        subcategory="running_shoes",
        brand="Nike",
        gender="men",
        color=color,
        sizes=["8", "9"],
        price=Decimal(price),
        currency="INR",
        availability="in_stock",
        field_provenance={"title": "test"},
    )


def test_query_understanding_accuracy_matches_hand_calculation() -> None:
    expected = ParsedIntent(
        query_text="running shoes",
        constraints=SearchConstraints(brand="Nike", color="black"),
        sorting_intent="price_asc",
    )
    actual = ParsedIntent(
        query_text="running shoes",
        constraints=SearchConstraints(brand="Nike", color="blue"),
        sorting_intent="price_asc",
    )
    result = query_understanding_field_accuracy(expected, actual)
    assert result.value == 3 / 4
    assert result.evidence.observed["mismatches"] == {
        "color": {"expected": "black", "actual": "blue"}
    }


def test_filter_accuracy_matches_hand_calculation() -> None:
    expected = SearchConstraints(brand="Nike", color="black", max_price=Decimal(3000))
    actual = SearchConstraints(brand="Nike", color="blue", max_price=Decimal(3000))
    result = filter_accuracy(expected, actual)
    assert result.value == 2 / 3


def test_missing_applied_filters_are_explicit_failure() -> None:
    result = filter_accuracy(SearchConstraints(brand="Nike"), None)
    assert result.value == 0.0
    assert result.passed is False


def test_filter_accuracy_is_unknown_without_expected_filters() -> None:
    result = filter_accuracy(SearchConstraints(), SearchConstraints())
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN


def test_constraint_satisfaction_matches_hand_calculation() -> None:
    products = [
        make_product("pass", color="black", price=2000),
        make_product("fail", color="blue", price=4000),
    ]
    constraints = SearchConstraints(color="black", max_price=Decimal(3000))
    result = constraint_satisfaction(products, constraints)
    assert result.value == 1 / 2
    assert result.passed is False
    assert result.evidence.observed["violations"] == {
        "fail": ["color", "max_price"]
    }


def test_constraint_satisfaction_passes_when_all_products_comply() -> None:
    products = [make_product("pass", color="black", price=2000)]
    result = constraint_satisfaction(products, SearchConstraints(color="black"))
    assert result.value == 1.0
    assert result.passed is True


def test_constraint_satisfaction_is_unknown_without_products() -> None:
    result = constraint_satisfaction([], SearchConstraints(color="black"))
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN


def test_constraint_satisfaction_is_unknown_without_constraints() -> None:
    result = constraint_satisfaction(
        [make_product("p-1", color="black", price=2000)],
        SearchConstraints(),
    )
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN
