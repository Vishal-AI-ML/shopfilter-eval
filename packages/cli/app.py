from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from packages.demo_search.engine import DemoSearchEngine
from packages.esci_pipeline.download import DownloadError, download_manifest
from packages.esci_pipeline.manifest import ManifestError, load_source_manifest
from packages.esci_pipeline.prepare import (
    EsciPreparationError,
    PreparationConfig,
    prepare_esci_subset,
    verify_processed_artifacts,
)
from packages.esci_pipeline.review import (
    EsciReviewError,
    create_review_packet,
    publish_source_validated_dataset,
)
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
from packages.tracing import (
    NoOpTraceProvider,
    TraceProvider,
    langfuse_provider_from_env,
)

app = typer.Typer(no_args_is_help=True, help="ShopFilter Eval command-line interface")
esci_app = typer.Typer(no_args_is_help=True, help="Prepare verified Amazon ESCI data")
app.add_typer(esci_app, name="esci")
console = Console()
DEFAULT_ARTIFACT_DIRECTORY = Path("artifacts/runs")
DEFAULT_ESCI_MANIFEST = Path("data/manifests/esci-amazon-science-2024-10-07.json")
DEFAULT_ESCI_RAW_ROOT = Path("data/raw")
DEFAULT_ESCI_OUTPUT_ROOT = Path("data/processed")


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


def _build_trace_provider(provider_name: str) -> TraceProvider:
    if provider_name == "noop":
        return NoOpTraceProvider()
    if provider_name == "langfuse":
        return langfuse_provider_from_env()
    raise ValueError(f"Unsupported trace provider: {provider_name}")


async def _run_evaluation(
    *,
    root: Path,
    dataset_name: str,
    system_name: str,
    trace_provider_name: str,
    top_k: int,
    seed: int,
    artifact_directory: Path,
) -> tuple[Path, int, int, dict[str, float | None], dict[str, int]]:
    catalog = load_catalog(root / "data" / "demo" / "catalog-v1.json")
    dataset = load_golden_dataset(
        root / "data" / "goldens" / f"{dataset_name}.json"
    )
    adapter = _build_adapter(system_name, catalog)
    trace_provider = _build_trace_provider(trace_provider_name)
    runner = EvaluationRunner(adapter, catalog, trace_provider)
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
    trace: Annotated[str, typer.Option(help="Trace provider: noop or langfuse")] = "noop",
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
                trace_provider_name=trace,
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


@esci_app.command("download")
def esci_download(
    manifest_path: Annotated[
        Path,
        typer.Option("--manifest", help="Pinned ESCI source manifest"),
    ] = DEFAULT_ESCI_MANIFEST,
    raw_dir: Annotated[
        Path,
        typer.Option(help="Immutable raw-data root"),
    ] = DEFAULT_ESCI_RAW_ROOT,
) -> None:
    """Download and checksum-verify the pinned official ESCI Parquet files."""
    root = Path.cwd()
    try:
        manifest = load_source_manifest(root / manifest_path)
        console.print(
            "Downloading approximately 1.2 GB of pinned ESCI data; existing valid files "
            "will be reused."
        )
        paths = download_manifest(manifest, root / raw_dir)
    except (DownloadError, ManifestError) as exc:
        console.print(f"[bold red]ESCI DOWNLOAD ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc
    for path in paths:
        console.print(f"[green]Verified:[/] {path}")


@esci_app.command("prepare")
def esci_prepare(
    target_products: Annotated[
        int,
        typer.Option(min=1, help="Minimum unique-product selection target"),
    ] = 1000,
    version: Annotated[
        str,
        typer.Option(help="Immutable processed artifact version"),
    ] = "esci-en-v1",
    seed: Annotated[int, typer.Option(help="Deterministic selection seed")] = 13,
    manifest_path: Annotated[
        Path,
        typer.Option("--manifest", help="Pinned ESCI source manifest"),
    ] = DEFAULT_ESCI_MANIFEST,
    raw_dir: Annotated[
        Path,
        typer.Option(help="Immutable raw-data root"),
    ] = DEFAULT_ESCI_RAW_ROOT,
    output_dir: Annotated[
        Path,
        typer.Option(help="Processed artifact root"),
    ] = DEFAULT_ESCI_OUTPUT_ROOT,
) -> None:
    """Build a deterministic English ESCI catalog and unapproved golden draft."""
    root = Path.cwd()
    try:
        manifest = load_source_manifest(root / manifest_path)
        destination = prepare_esci_subset(
            manifest,
            root / raw_dir,
            root / output_dir,
            PreparationConfig(
                version=version,
                target_products=target_products,
                seed=seed,
                locale=manifest.locale,
                version_flag=manifest.version_flag,
            ),
        )
        report = verify_processed_artifacts(destination)
    except (
        DownloadError,
        EsciPreparationError,
        FileExistsError,
        ManifestError,
        ValueError,
    ) as exc:
        console.print(f"[bold red]ESCI PREPARATION ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc
    console.print(f"[bold green]Prepared:[/] {destination}")
    console.print(
        f"Products: {report.actual_product_count} | Queries: {report.query_count} | "
        f"Judgments: {report.judgment_count} | Status: IN_REVIEW"
    )


@esci_app.command("review-create")
def esci_review_create(
    artifact_directory: Annotated[
        Path,
        typer.Argument(help="Verified processed ESCI artifact directory"),
    ],
    case_count: Annotated[
        int,
        typer.Option(min=2, help="Number of human-review candidates"),
    ] = 200,
    version: Annotated[
        str,
        typer.Option(help="Immutable review-dataset version"),
    ] = "esci-golden-v1",
    seed: Annotated[int, typer.Option(help="Deterministic review selection seed")] = 29,
    output_dir: Annotated[
        Path,
        typer.Option(help="Review packet output directory"),
    ] = Path("data/goldens"),
) -> None:
    """Select balanced cases and create an unapproved human-review packet."""
    try:
        draft_path, review_path, dataset = create_review_packet(
            artifact_directory,
            output_dir,
            case_count=case_count,
            seed=seed,
            version=version,
        )
    except (EsciReviewError, FileExistsError, ValueError) as exc:
        console.print(f"[bold red]ESCI REVIEW ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc
    train_count = sum(case.split == "train" for case in dataset.cases)
    test_count = len(dataset.cases) - train_count
    console.print(f"[bold green]Review draft:[/] {draft_path}")
    console.print(f"[bold green]Review document:[/] {review_path}")
    console.print(
        f"Cases: {len(dataset.cases)} | Train: {train_count} | Test: {test_count} | "
        "Status: IN_REVIEW"
    )


@esci_app.command("source-validate")
def esci_source_validate(
    artifact_directory: Annotated[
        Path,
        typer.Argument(help="Verified processed ESCI artifact directory"),
    ],
    draft_path: Annotated[
        Path,
        typer.Option("--draft", help="Selected review draft"),
    ] = Path("data/goldens/esci-golden-v1-draft.json"),
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Immutable SOURCE_VALIDATED output"),
    ] = Path("data/goldens/esci-golden-v1-source-validated.json"),
    expected_cases: Annotated[
        int,
        typer.Option(min=2, help="Required balanced case count"),
    ] = 200,
) -> None:
    """Publish ESCI source judgments after automated integrity validation."""
    try:
        dataset = publish_source_validated_dataset(
            draft_path,
            artifact_directory,
            output_path,
            expected_case_count=expected_cases,
        )
    except (EsciReviewError, FileExistsError, ValueError) as exc:
        console.print(f"[bold red]ESCI SOURCE VALIDATION ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc
    console.print(f"[bold green]Published:[/] {output_path}")
    console.print(
        f"Cases: {len(dataset.cases)} | Status: {dataset.status} | "
        f"Human reviewed: {dataset.validation_evidence['human_reviewed']}"
    )
    console.print(f"Content hash: {dataset.content_hash}")


@esci_app.command("verify")
def esci_verify(
    directory: Annotated[
        Path,
        typer.Argument(help="Processed ESCI artifact directory"),
    ],
) -> None:
    """Verify processed ESCI artifacts against their quality-report checksums."""
    try:
        report = verify_processed_artifacts(directory)
    except EsciPreparationError as exc:
        console.print(f"[bold red]ESCI VERIFICATION ERROR:[/] {exc}")
        raise typer.Exit(code=3) from exc
    console.print(
        f"[bold green]Verified:[/] {directory} | Products: "
        f"{report.actual_product_count} | Queries: {report.query_count}"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
