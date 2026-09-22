from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import (
    CaseType,
    load_golden_dataset,
    validate_golden_dataset,
)
from packages.evaluation_engine.models import SearchRequest
from packages.evaluation_engine.query_parser import parse_query
from packages.search_adapters.demo import DemoSearchAdapter

console = Console()


async def main() -> None:
    root = Path.cwd()
    catalog = load_catalog(root / "data" / "demo" / "catalog-v1.json")
    dataset = load_golden_dataset(
        root / "data" / "goldens" / "golden-v1-draft.json"
    )
    report = validate_golden_dataset(dataset, catalog)
    adapter = DemoSearchAdapter(DemoSearchEngine(catalog))

    table = Table(title="Golden V1 — 20-case review")
    table.add_column("Case")
    table.add_column("Type")
    table.add_column("Parser")
    table.add_column("Expected products")
    table.add_column("Actual products")
    table.add_column("Verdict")

    passed = 0
    expected_gaps = 0
    failed = 0

    for case in dataset.cases:
        parsed = parse_query(case.query)
        parser_ok = (
            parsed.query_text == case.expected_query_text
            and parsed.constraints == case.expected_constraints
            and parsed.sorting_intent == case.expected_sorting_intent
        )
        response = await adapter.search(SearchRequest(query=case.query, top_k=100))
        expected_ids = [item.product_id for item in case.expected_products]
        actual_ids = [item.product.product_id for item in response.products]

        if not parser_ok:
            verdict = "FAIL"
            failed += 1
        elif expected_ids and actual_ids == expected_ids:
            verdict = "PASS"
            passed += 1
        elif not expected_ids and not actual_ids:
            verdict = "PASS (negative)"
            passed += 1
        elif case.case_type == CaseType.CATALOG_QUALITY and not expected_ids:
            verdict = "EXPECTED GAP"
            expected_gaps += 1
        else:
            verdict = "FAIL"
            failed += 1

        table.add_row(
            case.case_id,
            case.case_type.value,
            "PASS" if parser_ok else "FAIL",
            ", ".join(expected_ids) or "None",
            ", ".join(actual_ids) or "None",
            verdict,
        )

    console.print(table)
    console.print(
        f"\nCases: {report['case_count']} | Passed: {passed} | "
        f"Expected gaps: {expected_gaps} | Failed: {failed}"
    )
    console.print(f"Hash valid: {report['hash_valid']}")
    console.print(f"Dataset status: {dataset.status.value}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
