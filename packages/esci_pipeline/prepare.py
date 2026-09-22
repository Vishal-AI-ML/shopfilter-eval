
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

import pyarrow.dataset as ds  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import ValidationError

from packages.esci_pipeline.download import sha256_file, verify_source_file
from packages.esci_pipeline.manifest import EsciSourceManifest
from packages.esci_pipeline.models import (
    EsciDraftCase,
    EsciDraftDataset,
    PreparationReport,
    ProcessedFileRecord,
)
from packages.evaluation_engine.models import (
    Availability,
    Catalog,
    ExpectedProduct,
    Product,
    RelevanceLabel,
)

PIPELINE_VERSION = "esci-pipeline-v1"
_REQUIRED_EXAMPLE_COLUMNS = {
    "query",
    "query_id",
    "product_id",
    "product_locale",
    "esci_label",
    "small_version",
    "large_version",
    "split",
}
_REQUIRED_PRODUCT_COLUMNS = {
    "product_id",
    "product_title",
    "product_description",
    "product_bullet_point",
    "product_brand",
    "product_color",
    "product_locale",
}


class EsciPreparationError(RuntimeError):
    """Raised when ESCI preparation cannot produce a validated immutable subset."""


@dataclass(frozen=True)
class PreparationConfig:
    version: str = "esci-en-v1"
    target_products: int = 1000
    seed: int = 13
    locale: str = "us"
    version_flag: str = "small_version"

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        if self.target_products < 1:
            raise ValueError("target_products must be positive")
        if self.locale != "us":
            raise ValueError("Phase 13 supports only the ESCI English/US locale")
        if self.version_flag not in {"small_version", "large_version"}:
            raise ValueError("version_flag must be small_version or large_version")


@dataclass
class _QueryGroup:
    query_id: int
    query: str
    split: Literal["train", "test"]
    judgments: list[tuple[str, str]]


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stable_key(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def _validate_columns(path: Path, required: set[str]) -> None:
    available = set(pq.read_schema(path).names)
    missing = sorted(required - available)
    if missing:
        raise EsciPreparationError(f"Missing columns in {path.name}: {', '.join(missing)}")


def _load_query_groups(path: Path, config: PreparationConfig) -> list[_QueryGroup]:
    _validate_columns(path, _REQUIRED_EXAMPLE_COLUMNS)
    dataset = ds.dataset(path, format="parquet")
    predicate = (ds.field("product_locale") == config.locale) & (
        ds.field(config.version_flag) == 1
    )
    table = dataset.to_table(
        columns=["query_id", "query", "product_id", "esci_label", "split"],
        filter=predicate,
    )
    groups: dict[int, _QueryGroup] = {}
    for row in table.to_pylist():
        query_id = int(row["query_id"])
        query = str(row["query"] or "").strip()
        product_id = str(row["product_id"] or "").strip()
        label = str(row["esci_label"] or "").strip()
        split = str(row["split"] or "").strip()
        if not query or not product_id or label not in {"E", "S", "C", "I"}:
            continue
        if split not in {"train", "test"}:
            continue
        typed_split = cast(Literal["train", "test"], split)
        group = groups.setdefault(
            query_id, _QueryGroup(query_id, query, typed_split, [])
        )
        if group.query != query or group.split != split:
            raise EsciPreparationError(f"Inconsistent rows for query_id {query_id}")
        group.judgments.append((product_id, label))
    if not groups:
        raise EsciPreparationError("No matching English ESCI query groups were found")
    return list(groups.values())


def _select_groups(groups: list[_QueryGroup], config: PreparationConfig) -> list[_QueryGroup]:
    by_split: dict[str, list[_QueryGroup]] = {"train": [], "test": []}
    for group in groups:
        by_split[group.split].append(group)
    for split_groups in by_split.values():
        split_groups.sort(
            key=lambda group: (
                -len({label for _, label in group.judgments}),
                _stable_key(config.seed, str(group.query_id)),
            )
        )

    selected: list[_QueryGroup] = []
    selected_products: set[str] = set()
    index = 0
    while len(selected_products) < config.target_products:
        made_progress = False
        for split in ("train", "test"):
            candidates = by_split[split]
            if index < len(candidates):
                group = candidates[index]
                selected.append(group)
                selected_products.update(product_id for product_id, _ in group.judgments)
                made_progress = True
                if len(selected_products) >= config.target_products:
                    break
        if not made_progress:
            raise EsciPreparationError(
                f"Only {len(selected_products)} unique products are available for selection"
            )
        index += 1
    return selected


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_products(path: Path, product_ids: set[str], locale: str) -> dict[str, dict[str, Any]]:
    _validate_columns(path, _REQUIRED_PRODUCT_COLUMNS)
    dataset = ds.dataset(path, format="parquet")
    predicate = (ds.field("product_locale") == locale) & ds.field(
        "product_id"
    ).isin(sorted(product_ids))
    table = dataset.to_table(
        columns=[
            "product_id",
            "product_title",
            "product_description",
            "product_bullet_point",
            "product_brand",
            "product_color",
            "product_locale",
        ],
        filter=predicate,
    )
    return {str(row["product_id"]): row for row in table.to_pylist()}


def _normalize_products(
    raw_products: dict[str, dict[str, Any]],
    selected_ids: set[str],
    manifest: EsciSourceManifest,
    config: PreparationConfig,
) -> tuple[list[Product], list[str]]:
    missing = sorted(selected_ids - raw_products.keys())
    if missing:
        preview = ", ".join(missing[:5])
        raise EsciPreparationError(f"Selected products missing from product data: {preview}")

    products: list[Product] = []
    missing_titles: list[str] = []
    for product_id in sorted(selected_ids):
        source = raw_products[product_id]
        title = _clean_optional(source.get("product_title"))
        if title is None:
            missing_titles.append(product_id)
            continue
        description = _clean_optional(source.get("product_description"))
        bullet_point = _clean_optional(source.get("product_bullet_point"))
        products.append(
            Product(
                product_id=product_id,
                title=title,
                description=description or bullet_point,
                category="unknown",
                brand=_clean_optional(source.get("product_brand")),
                color=_clean_optional(source.get("product_color")),
                price=Decimal("0.00"),
                currency="USD",
                availability=Availability.UNKNOWN,
                attributes={"bullet_point": bullet_point} if bullet_point else {},
                source_metadata={
                    "dataset": manifest.dataset_name,
                    "manifest_id": manifest.manifest_id,
                    "source_commit": manifest.commit,
                    "locale": config.locale,
                    "source_file": "shopping_queries_dataset_products.parquet",
                    "license": manifest.license,
                },
                field_provenance={
                    "product_id": "ESCI:product_id",
                    "title": "ESCI:product_title",
                    "description": (
                        "ESCI:product_description"
                        if description
                        else "ESCI:product_bullet_point"
                    ),
                    "brand": "ESCI:product_brand",
                    "color": "ESCI:product_color",
                    "attributes.bullet_point": "ESCI:product_bullet_point",
                    "category": "synthetic_placeholder:not_provided_by_esci",
                    "price": "synthetic_placeholder:not_provided_by_esci",
                    "currency": "synthetic_placeholder:not_provided_by_esci",
                    "availability": "synthetic_placeholder:not_provided_by_esci",
                },
            )
        )
    return products, missing_titles


def _build_draft_dataset(
    groups: list[_QueryGroup],
    valid_product_ids: set[str],
    manifest: EsciSourceManifest,
    config: PreparationConfig,
) -> EsciDraftDataset:
    cases: list[EsciDraftCase] = []
    for group in sorted(groups, key=lambda item: item.query_id):
        judgments = [
            ExpectedProduct(product_id=product_id, relevance=RelevanceLabel(label))
            for product_id, label in group.judgments
            if product_id in valid_product_ids
        ]
        if not judgments:
            continue
        cases.append(
            EsciDraftCase(
                case_id=f"ESCI-{group.query_id}",
                query_id=group.query_id,
                query=group.query,
                split=group.split,
                expected_products=judgments,
                source_provenance={
                    "query": "ESCI:shopping_queries_dataset_examples.parquet:query",
                    "judgments": "ESCI:shopping_queries_dataset_examples.parquet:esci_label",
                    "source_commit": manifest.commit,
                },
            )
        )
    base = {
        "dataset_id": f"{config.version}-draft",
        "version": config.version,
        "status": "IN_REVIEW",
        "catalog_id": f"{config.version}-catalog",
        "catalog_version": config.version,
        "source_manifest_id": manifest.manifest_id,
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    return EsciDraftDataset.model_validate({**base, "content_hash": _canonical_hash(base)})


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _record(path: Path) -> ProcessedFileRecord:
    return ProcessedFileRecord(
        name=path.name,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def prepare_esci_subset(
    manifest: EsciSourceManifest,
    raw_root: str | Path,
    output_root: str | Path,
    config: PreparationConfig,
) -> Path:
    if config.locale != manifest.locale or config.version_flag != manifest.version_flag:
        raise EsciPreparationError("Preparation config does not match the pinned source manifest")
    raw_directory = Path(raw_root) / manifest.manifest_id
    examples_path = raw_directory / "shopping_queries_dataset_examples.parquet"
    products_path = raw_directory / "shopping_queries_dataset_products.parquet"
    for source in manifest.files:
        verify_source_file(raw_directory / source.name, source)

    destination = Path(output_root) / config.version / f"products-{config.target_products}"
    if destination.exists():
        raise FileExistsError(f"Processed artifact is immutable and already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        groups = _select_groups(_load_query_groups(examples_path, config), config)
        selected_ids = {
            product_id for group in groups for product_id, _ in group.judgments
        }
        raw_products = _load_products(products_path, selected_ids, config.locale)
        products, missing_titles = _normalize_products(
            raw_products, selected_ids, manifest, config
        )
        if len(products) < config.target_products:
            raise EsciPreparationError(
                "Validated products fell below the requested target after missing-title "
                "rejection"
            )
        valid_ids = {product.product_id for product in products}
        catalog = Catalog(
            catalog_id=f"{config.version}-catalog",
            version=config.version,
            products=products,
        )
        draft = _build_draft_dataset(groups, valid_ids, manifest, config)

        catalog_path = destination / "catalog.json"
        draft_path = destination / "golden-draft.json"
        source_path = destination / "source-manifest.json"
        _write_json(catalog_path, catalog.model_dump(mode="json"))
        _write_json(draft_path, draft.model_dump(mode="json"))
        _write_json(source_path, manifest.model_dump(mode="json"))

        labels = Counter(
            expected.relevance.value
            for case in draft.cases
            for expected in case.expected_products
        )
        splits = Counter(case.split for case in draft.cases)
        records = [_record(catalog_path), _record(draft_path), _record(source_path)]
        report = PreparationReport(
            pipeline_version=PIPELINE_VERSION,
            source_manifest_id=manifest.manifest_id,
            source_commit=manifest.commit,
            locale=config.locale,
            version_flag=config.version_flag,
            requested_product_count=config.target_products,
            actual_product_count=len(products),
            query_count=len(draft.cases),
            judgment_count=sum(len(case.expected_products) for case in draft.cases),
            split_counts=dict(sorted(splits.items())),
            label_counts=dict(sorted(labels.items())),
            missing_title_count=len(missing_titles),
            synthetic_fields=["category", "price", "currency", "availability"],
            output_files=records,
            selection={
                "algorithm": "label-diversity-then-seeded-hash; alternating train/test",
                "seed": config.seed,
                "preserves_complete_query_groups": True,
                "target_is_minimum_before_missing-title_validation": True,
            },
        )
        report_path = destination / "quality-report.json"
        _write_json(report_path, report.model_dump(mode="json"))
        verify_processed_artifacts(destination)
    except Exception as exc:
        for child in destination.iterdir():
            child.unlink()
        destination.rmdir()
        if isinstance(exc, EsciPreparationError):
            raise
        raise EsciPreparationError("Unable to prepare ESCI subset") from exc
    return destination


def verify_processed_artifacts(directory: str | Path) -> PreparationReport:
    artifact_directory = Path(directory)
    report_path = artifact_directory / "quality-report.json"
    try:
        report = PreparationReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise EsciPreparationError("Invalid or missing ESCI quality report") from exc
    for record in report.output_files:
        path = artifact_directory / record.name
        if not path.is_file():
            raise EsciPreparationError(f"Missing processed artifact: {record.name}")
        if path.stat().st_size != record.size_bytes or sha256_file(path) != record.sha256:
            raise EsciPreparationError(f"Processed artifact failed verification: {record.name}")
    return report
