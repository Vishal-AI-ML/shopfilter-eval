from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import CatalogLoadError, load_catalog
from packages.evaluation_engine.datasets import GoldenDatasetError, load_golden_dataset
from packages.evaluation_engine.models import Catalog
from packages.evaluation_engine.runner import EvaluationRunner, write_run_artifact
from packages.search_adapters.base import SearchAdapter, SearchAdapterError
from packages.search_adapters.demo import DemoSearchAdapter
from packages.search_adapters.faults import (
    FaultInjectingSearchAdapter,
    load_failure_profiles,
)

app = typer.Typer(no_args_is_help=True, help="ShopFilter Eval command-line interface")
console = Console()
DEFAULT_ARTIFACT_DIRECTORY = Path("artifacts/runs")


@app.callback()
def cli() -> None:
    """Evaluate e-commerce search quality with reproducible evidence."""


def _format_metric(value: float | None) -> str:
    return "UNKNOWN" if value is None else f"{value:.4f}"


def _build_adapter(system_name: str, catalog: Catalog) -> SearchAdapter:
    base = DemoSearchAdapter(DemoSearchEngine(catalog))
    if system_name == "demo-v1":
        return base
    profiles = load_failure_profiles()
    if system_name not in profiles:
        raise ValueError(f"Unsupported local system: {system_name}")
    return FaultInjectingSearchAdapter(base, catalog, profiles[system_name])


async def _run_evaluation(
    *,
    root: Path,
    dataset_name: str,
    system_name: str,
    top_k: int,
    seed: int,
    artifact_directory: Path,
) -> tuple[Path, int, int, dict[str, float | None], dict[str, int]]:
    catalog = load_catalog(root / "data" / "demo" / "catalog-v1.json")
    dataset = load_golden_dataset(
        root / "data" / "goldens" / f"{dataset_name}.json"
    )
    adapter = _build_adapter(system_name, catalog)
    runner = EvaluationRunner(adapter, catalog)
    artifact = await runner.run(
        dataset,
        search_system_version=system_name,
        top_k=top_k,
        seed=seed,
    )
    artifact_path = write_run_artifact(artifact, artifact_directory)
    return (
        artifact_path,
        artifact.passed_case_count,
        artifact.failed_case_count,
        artifact.aggregate_metrics,
        artifact.failure_counts,
    )


@app.command()
def evaluate(
    dataset: Annotated[str, typer.Option(help="Approved dataset name")] = "golden-v1",
    system: Annotated[str, typer.Option(help="Search-system version")] = "demo-v1",
    top_k: Annotated[int, typer.Option(min=1, help="Evaluation cutoff")] = 10,
    seed: Annotated[int, typer.Option(help="Deterministic seed")] = 0,
    artifact_dir: Annotated[
        Path,
        typer.Option(help="Run artifact directory"),
    ] = DEFAULT_ARTIFACT_DIRECTORY,
) -> None:
    """Run the approved golden dataset through a normalized Search Adapter."""
    root = Path.cwd()
    try:
        artifact_path, passed, failed, metrics, failure_counts = asyncio.run(
            _run_evaluation(
                root=root,
                dataset_name=dataset,
                system_name=system,
                top_k=top_k,
                seed=seed,
                artifact_directory=root / artifact_dir,
            )
        )
    except (
        CatalogLoadError,
        FileExistsError,
        GoldenDatasetError,
        SearchAdapterError,
        ValueError,
    ) as exc:
        console.print(f"[bold red]EXECUTION ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc

    table = Table(title="ShopFilter Evaluation Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for metric_name, value in metrics.items():
        table.add_row(metric_name, _format_metric(value))
    console.print(table)
    if failure_counts:
        failure_table = Table(title="Evidence-based failures")
        failure_table.add_column("Failure type")
        failure_table.add_column("Cases", justify="right")
        for failure_type, count in failure_counts.items():
            failure_table.add_row(failure_type, str(count))
        console.print(failure_table)
    console.print(f"Cases: {passed + failed} | Passed: {passed} | Failed: {failed}")
    console.print(f"Artifact: {artifact_path}")
    if failed:
        console.print("[bold yellow]Verdict: REVIEW[/]")
        raise typer.Exit(code=2)
    console.print("[bold green]Verdict: PASS[/]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
