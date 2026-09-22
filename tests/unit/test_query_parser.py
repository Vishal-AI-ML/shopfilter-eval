from decimal import Decimal

import pytest

from packages.evaluation_engine.models import Availability
from packages.evaluation_engine.query_parser import parse_query


@pytest.mark.parametrize(
    ("query", "field", "expected"),
    [
        ("comfortable shoes", "category", "shoes"),
        ("winter clothing", "category", "clothing"),
        ("new electronics", "category", "electronics"),
        ("travel bags", "category", "bags"),
        ("classic watches", "category", "watches"),
        ("running shoes", "subcategory", "running_shoes"),
        ("casual trainers", "subcategory", "sneakers"),
        ("black dress shoes", "subcategory", "formal_shoes"),
        ("walking shoes", "subcategory", "walking_shoes"),
        ("cotton t-shirt", "subcategory", "t_shirts"),
        ("blue denim", "subcategory", "jeans"),
        ("wireless earbuds", "subcategory", "earbuds"),
        ("office notebook computer", "subcategory", "laptops"),
        ("travel rucksack", "subcategory", "backpacks"),
        ("health fitness tracker", "subcategory", "fitness_band"),
        ("nike running shoes", "brand", "Nike"),
        ("ONE PLUS phone", "brand", "OnePlus"),
        ("boat earbuds", "brand", "boAt"),
        ("men shoes", "gender", "men"),
        ("men's shoes", "gender", "men"),
        ("male shoes", "gender", "men"),
        ("women shoes", "gender", "women"),
        ("female jacket", "gender", "women"),
        ("unisex watch", "gender", "unisex"),
        ("gray sneakers", "color", "grey"),
        ("navy blue bag", "color", "navy"),
        ("silver watch", "color", "silver"),
        ("beige clothing", "color", "beige"),
        ("shoes below ₹3,000", "max_price", Decimal(3000)),
        ("shoes under INR 2500", "max_price", Decimal(2500)),
        ("shoes less than 2000 rupees", "max_price", Decimal(2000)),
        ("shoes up to 2999", "max_price", Decimal(2999)),
        ("phone max Rs. 20000", "max_price", Decimal(20000)),
        ("watch above ₹1000", "min_price", Decimal(1000)),
        ("watch over INR 1500", "min_price", Decimal(1500)),
        ("watch more than 2000 rupees", "min_price", Decimal(2000)),
        ("watch at least 999", "min_price", Decimal(999)),
        ("watch minimum Rs 1200", "min_price", Decimal(1200)),
        ("shoes size 9", "size", "9"),
        ("shoes size: 8.5", "size", "8.5"),
        ("shirt size xl", "size", "XL"),
        ("boots UK size 10", "size", "10"),
        ("available running shoes", "availability", Availability.IN_STOCK),
        ("ready to ship laptop", "availability", Availability.IN_STOCK),
        ("out of stock watch", "availability", Availability.OUT_OF_STOCK),
        ("cheapest sneakers", "sorting_intent", "price_asc"),
        ("price high to low watches", "sorting_intent", "price_desc"),
        ("top rated headphones", "sorting_intent", "rating_desc"),
    ],
)
def test_parser_expressions(query: str, field: str, expected: object) -> None:
    parsed = parse_query(query)
    if field == "sorting_intent":
        actual = parsed.sorting_intent
    else:
        actual = getattr(parsed.constraints, field)
    assert actual == expected


def test_full_query_matches_normalized_example() -> None:
    parsed = parse_query("nike men's black running shoes below ₹3000 size 9")
    assert parsed.query_text == "running shoes"
    assert parsed.constraints.category == "shoes"
    assert parsed.constraints.subcategory == "running_shoes"
    assert parsed.constraints.brand == "Nike"
    assert parsed.constraints.gender == "men"
    assert parsed.constraints.color == "black"
    assert parsed.constraints.max_price == Decimal(3000)
    assert parsed.constraints.size == "9"


def test_price_range() -> None:
    parsed = parse_query("running shoes between ₹1,500 and INR 3,000")
    assert parsed.constraints.min_price == Decimal(1500)
    assert parsed.constraints.max_price == Decimal(3000)


def test_subcategory_infers_category() -> None:
    parsed = parse_query("wireless earbuds")
    assert parsed.constraints.subcategory == "earbuds"
    assert parsed.constraints.category == "electronics"


def test_unknown_value_is_not_guessed() -> None:
    parsed = parse_query("teal trail shoes")
    assert parsed.constraints.color is None
    assert "teal" in parsed.query_text


def test_same_input_is_deterministic() -> None:
    query = "adidas women's white running shoes under 3000 size 7 available"
    assert parse_query(query) == parse_query(query)


def test_blank_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="blank"):
        parse_query("   ")
