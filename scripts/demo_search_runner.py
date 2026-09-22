from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.models import SearchRequest
from packages.search_adapters.demo import DemoSearchAdapter

console = Console()


async def run(query: str, top_k: int) -> None:
    root = Path.cwd()
    catalog = load_catalog(root / "data" / "demo" / "catalog-v1.json")
    adapter = DemoSearchAdapter(DemoSearchEngine(catalog))
    response = await adapter.search(SearchRequest(query=query, top_k=top_k))

    console.print(f"\n[bold blue]Query:[/] {response.query}")
    if response.interpreted_query is not None:
        console.print(
            "[bold]Remaining query:[/] "
            f"{response.interpreted_query.query_text or '(empty)'}"
        )
    if response.applied_filters is not None:
        filters = response.applied_filters.model_dump(exclude_none=True, mode="json")
        console.print(f"[bold]Applied filters:[/] {filters or '{}'}")

    table = Table(title=f"Top {top_k} results")
    table.add_column("Rank", justify="right")
    table.add_column("Product ID")
    table.add_column("Title")
    table.add_column("Price", justify="right")
    table.add_column("Score", justify="right")

    for result in response.products:
        product = result.product
        table.add_row(
            str(result.rank),
            product.product_id,
            product.title,
            f"{product.currency} {product.price}",
            f"{result.score:.3f}",
        )

    console.print(table)
    console.print(
        f"Retrieved: {len(response.retrieved_candidates or [])} | "
        f"After filters: {len(response.filtered_candidates or [])} | "
        f"Latency: {response.latency_ms:.2f} ms\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview ShopFilter demo search")
    parser.add_argument("query", help="Shopping query to evaluate")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args.query, args.top_k))


if __name__ == "__main__":
    main()
