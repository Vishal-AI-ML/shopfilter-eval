from __future__ import annotations

import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.evaluation_engine.models import (
    Availability,
    ParsedIntent,
    SearchConstraints,
)

VOCAB_PATH = Path(__file__).with_name("query_vocab.json")
NUMBER = r"(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)"
CURRENCY_PREFIX = r"(?:₹|inr\s*|rs\.?\s*)?"
CURRENCY_SUFFIX = r"(?:\s*(?:rupees?|rs\.?))?"
MAX_PRICE_RE = re.compile(
    rf"\b(?:under|below|less\s+than|up\s*to|maximum|max)\s*{CURRENCY_PREFIX}{NUMBER}{CURRENCY_SUFFIX}",
    re.IGNORECASE,
)
MIN_PRICE_RE = re.compile(
    rf"\b(?:above|over|more\s+than|at\s+least|minimum|min)\s*{CURRENCY_PREFIX}{NUMBER}{CURRENCY_SUFFIX}",
    re.IGNORECASE,
)
RANGE_PRICE_RE = re.compile(
    rf"\bbetween\s+{CURRENCY_PREFIX}(?P<minimum>\d+(?:,[0-9][0-9][0-9])*(?:\.\d+)?)"
    rf"{CURRENCY_SUFFIX}\s+and\s+{CURRENCY_PREFIX}(?P<maximum>\d+(?:,[0-9][0-9][0-9])*(?:\.\d+)?){CURRENCY_SUFFIX}",
    re.IGNORECASE,
)
SIZE_RE = re.compile(r"\b(?:uk\s+size|size)\s*[:=-]?\s*(?P<size>\d+(?:\.5)?|[smlx]{1,3})\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_vocabulary() -> dict[str, Any]:
    return json.loads(VOCAB_PATH.read_text(encoding="utf-8"))


def _alias_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.IGNORECASE)


def _find_alias(text: str, mapping: dict[str, list[str]]) -> tuple[str | None, tuple[int, int] | None]:
    candidates: list[tuple[int, int, str]] = []
    for canonical, aliases in mapping.items():
        for alias in aliases:
            match = _alias_pattern(alias).search(text)
            if match:
                candidates.append((match.start(), -len(alias), canonical))
    if not candidates:
        return None, None
    start, negative_length, canonical = min(candidates)
    return canonical, (start, start - negative_length)


def _find_subcategory(text: str, mapping: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    candidates: list[tuple[int, int, str, str]] = []
    for canonical, config in mapping.items():
        for alias in config["aliases"]:
            match = _alias_pattern(alias).search(text)
            if match:
                candidates.append((match.start(), -len(alias), canonical, config["category"]))
    if not candidates:
        return None, None
    _, _, subcategory, category = min(candidates)
    return subcategory, category


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _clean_remaining_query(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = " "
    cleaned = "".join(chars)
    cleaned = re.sub(r"[,:;|]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned


def parse_query(query: str) -> ParsedIntent:
    original = query.strip()
    if not original:
        raise ValueError("query cannot be blank")
    text = original.replace("’", "'")
    vocab = load_vocabulary()
    removable_spans: list[tuple[int, int]] = []

    subcategory, inferred_category = _find_subcategory(text, vocab["subcategories"])
    category, _ = _find_alias(text, vocab["categories"])
    category = inferred_category or category

    brand, span = _find_alias(text, vocab["brands"])
    if span:
        removable_spans.append(span)
    gender, span = _find_alias(text, vocab["genders"])
    if span:
        removable_spans.append(span)
    color, span = _find_alias(text, vocab["colors"])
    if span:
        removable_spans.append(span)

    availability_name, span = _find_alias(text, vocab["availability"])
    if span:
        removable_spans.append(span)
    availability = Availability(availability_name) if availability_name else None

    sorting_intent, span = _find_alias(text, vocab["sorting"])
    if span:
        removable_spans.append(span)

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    range_match = RANGE_PRICE_RE.search(text)
    if range_match:
        min_price = _decimal(range_match.group("minimum"))
        max_price = _decimal(range_match.group("maximum"))
        removable_spans.append(range_match.span())
    else:
        min_match = MIN_PRICE_RE.search(text)
        max_match = MAX_PRICE_RE.search(text)
        if min_match:
            min_price = _decimal(min_match.group("amount"))
            removable_spans.append(min_match.span())
        if max_match:
            max_price = _decimal(max_match.group("amount"))
            removable_spans.append(max_match.span())

    size: str | None = None
    size_match = SIZE_RE.search(text)
    if size_match:
        size = size_match.group("size").upper()
        removable_spans.append(size_match.span())

    constraints = SearchConstraints(
        category=category,
        subcategory=subcategory,
        brand=brand,
        gender=gender,
        color=color,
        min_price=min_price,
        max_price=max_price,
        size=size,
        availability=availability,
    )
    return ParsedIntent(
        query_text=_clean_remaining_query(text, removable_spans),
        constraints=constraints,
        sorting_intent=sorting_intent,
    )
