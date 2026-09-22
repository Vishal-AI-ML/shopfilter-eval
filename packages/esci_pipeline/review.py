
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.esci_pipeline.download import sha256_file
from packages.esci_pipeline.models import EsciDraftCase, EsciDraftDataset
from packages.evaluation_engine.catalog import CatalogLoadError, load_catalog
from packages.evaluation_engine.models import ExpectedProduct


class EsciReviewError(RuntimeError):
    """Raised when an ESCI review packet cannot be created or validated."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stable_key(seed: int, case: EsciDraftCase) -> str:
    return hashlib.sha256(f"{seed}:{case.case_id}".encode()).hexdigest()


def compute_draft_hash(dataset: EsciDraftDataset) -> str:
    return _canonical_hash(dataset.model_dump(mode="json", exclude={"content_hash"}))


def load_verified_draft(path: str | Path) -> EsciDraftDataset:
    draft_path = Path(path)
    try:
        dataset = EsciDraftDataset.model_validate_json(draft_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise EsciReviewError(f"Unable to load ESCI draft: {draft_path}") from exc
    if compute_draft_hash(dataset) != dataset.content_hash:
        raise EsciReviewError("ESCI draft content hash does not match its contents")
    return dataset


def select_review_cases(
    source: EsciDraftDataset,
    *,
    case_count: int = 200,
    seed: int = 29,
    version: str = "esci-golden-v1",
) -> EsciDraftDataset:
    if case_count < 2:
        raise ValueError("case_count must be at least 2")
    if not version.strip():
        raise ValueError("version cannot be blank")

    train_target = (case_count + 1) // 2
    test_target = case_count // 2
    by_split = {
        split: [case for case in source.cases if case.split == split]
        for split in ("train", "test")
    }
    if len(by_split["train"]) < train_target or len(by_split["test"]) < test_target:
        raise EsciReviewError("Not enough train/test candidates for the requested balanced review set")

    def ranking_key(case: EsciDraftCase) -> tuple[int, str]:
        diversity = len({expected.relevance for expected in case.expected_products})
        return (-diversity, _stable_key(seed, case))

    selected = [
        *sorted(by_split["train"], key=ranking_key)[:train_target],
        *sorted(by_split["test"], key=ranking_key)[:test_target],
    ]
    selected.sort(key=lambda case: case.case_id)
    base = {
        "dataset_id": f"{version}-draft",
        "version": version,
        "status": "IN_REVIEW",
        "catalog_id": source.catalog_id,
        "catalog_version": source.catalog_version,
        "source_manifest_id": source.source_manifest_id,
        "cases": [case.model_dump(mode="json") for case in selected],
    }
    return EsciDraftDataset.model_validate({**base, "content_hash": _canonical_hash(base)})


def _escape_markdown(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def render_review_markdown(
    dataset: EsciDraftDataset,
    catalog_path: str | Path,
    *,
    source_catalog_sha256: str,
    selection_seed: int,
) -> str:
    try:
        catalog = load_catalog(catalog_path)
    except CatalogLoadError as exc:
        raise EsciReviewError("Unable to load the review catalog") from exc
    products = {product.product_id: product for product in catalog.products}
    missing = sorted(
        {
            expected.product_id
            for case in dataset.cases
            for expected in case.expected_products
            if expected.product_id not in products
        }
    )
    if missing:
        raise EsciReviewError(f"Review cases reference missing catalog products: {', '.join(missing[:5])}")

    split_counts = Counter(case.split for case in dataset.cases)
    label_counts = Counter(
        expected.relevance.value
        for case in dataset.cases
        for expected in case.expected_products
    )
    lines = [
        "# ESCI Golden V1 — Human Review Packet",
        "",
        "> This document is a review aid, not an approved dataset. Every case remains `IN_REVIEW` until explicit human approval and publication.",
        "",
        "## Review contract",
        "",
        f"- Dataset version: `{dataset.version}`",
        f"- Dataset content hash: `{dataset.content_hash}`",
        f"- Catalog: `{dataset.catalog_id}` / `{dataset.catalog_version}`",
        f"- Source catalog SHA-256: `{source_catalog_sha256}`",
        f"- Source manifest: `{dataset.source_manifest_id}`",
        f"- Selection seed: `{selection_seed}`",
        f"- Cases: `{len(dataset.cases)}`",
        f"- Split: train `{split_counts['train']}`, test `{split_counts['test']}`",
        "- Labels: " + ", ".join(f"{label} `{label_counts[label]}`" for label in ("E", "S", "C", "I")),
        "",
        "For each case, inspect the query and every source judgment. Mark exactly one decision. Rejection requires a note. Do not approve cases merely because they came from ESCI.",
        "",
        "---",
    ]
    for index, case in enumerate(dataset.cases, start=1):
        lines.extend(
            [
                "",
                f"## {index:03d}. {case.case_id} — {_escape_markdown(case.query)}",
                "",
                f"- Split: `{case.split}`",
                f"- Query ID: `{case.query_id}`",
                f"- Judgments: `{len(case.expected_products)}`",
                "- Decision: [ ] APPROVE  [ ] REJECT",
                "- Reviewer notes:",
                "",
                "| # | Product ID | Label | Title | Brand | Color |",
                "|---:|---|:---:|---|---|---|",
            ]
        )
        for rank, expected in enumerate(case.expected_products, start=1):
            product = products[expected.product_id]
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(rank),
                        _escape_markdown(product.product_id),
                        expected.relevance.value,
                        _escape_markdown(product.title),
                        _escape_markdown(product.brand),
                        _escape_markdown(product.color),
                    ]
                )
                + " |"
            )
        lines.extend(["", "---"])
    return "\n".join(lines) + "\n"


def create_review_packet(
    artifact_directory: str | Path,
    output_directory: str | Path,
    *,
    case_count: int = 200,
    seed: int = 29,
    version: str = "esci-golden-v1",
) -> tuple[Path, Path, EsciDraftDataset]:
    artifact_path = Path(artifact_directory)
    output_path = Path(output_directory)
    draft_path = output_path / f"{version}-draft.json"
    review_path = output_path / f"{version}-review.md"
    if draft_path.exists() or review_path.exists():
        raise FileExistsError("Review packet is immutable and already exists")

    source = load_verified_draft(artifact_path / "golden-draft.json")
    selected = select_review_cases(
        source, case_count=case_count, seed=seed, version=version
    )
    try:
        report = json.loads(
            (artifact_path / "quality-report.json").read_text(encoding="utf-8")
        )
        catalog_record = next(
            item for item in report["output_files"] if item["name"] == "catalog.json"
        )
        catalog_sha256 = str(catalog_record["sha256"])
        if len(catalog_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in catalog_sha256
        ):
            raise ValueError("invalid catalog SHA-256")
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        KeyError,
        StopIteration,
        TypeError,
    ) as exc:
        raise EsciReviewError("Unable to read the source catalog checksum") from exc

    markdown = render_review_markdown(
        selected,
        artifact_path / "catalog.json",
        source_catalog_sha256=catalog_sha256,
        selection_seed=seed,
    )
    output_path.mkdir(parents=True, exist_ok=True)
    try:
        draft_path.write_text(
            json.dumps(selected.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        review_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        draft_path.unlink(missing_ok=True)
        review_path.unlink(missing_ok=True)
        raise EsciReviewError("Unable to write ESCI review packet") from exc
    return draft_path, review_path, selected


class SourceValidatedCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    query_id: int
    query: str = Field(min_length=1)
    locale: Literal["us"] = "us"
    split: Literal["train", "test"]
    expected_products: list[ExpectedProduct]
    validation_status: Literal["SOURCE_VALIDATED"] = "SOURCE_VALIDATED"
    source_provenance: dict[str, str]


class SourceValidatedDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["SOURCE_VALIDATED"] = "SOURCE_VALIDATED"
    catalog_id: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    source_manifest_id: str = Field(min_length=1)
    source_draft_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_catalog_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_evidence: dict[str, Any]
    cases: list[SourceValidatedCase]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def compute_source_validated_hash(dataset: SourceValidatedDataset) -> str:
    return _canonical_hash(dataset.model_dump(mode="json", exclude={"content_hash"}))


def _verify_artifact_record(
    artifact_directory: Path,
    records: dict[str, dict[str, Any]],
    name: str,
) -> str:
    try:
        record = records[name]
        expected_hash = str(record["sha256"])
        expected_size = int(record["size_bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EsciReviewError(f"Missing quality-report record for {name}") from exc
    path = artifact_directory / name
    if not path.is_file() or path.stat().st_size != expected_size:
        raise EsciReviewError(f"Source artifact size verification failed: {name}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise EsciReviewError(f"Source artifact checksum verification failed: {name}")
    return actual_hash


def publish_source_validated_dataset(
    selected_draft_path: str | Path,
    artifact_directory: str | Path,
    output_path: str | Path,
    *,
    expected_case_count: int = 200,
) -> SourceValidatedDataset:
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Published source-validated dataset already exists: {destination}")
    artifact_path = Path(artifact_directory)
    selected = load_verified_draft(selected_draft_path)
    source = load_verified_draft(artifact_path / "golden-draft.json")

    if len(selected.cases) != expected_case_count:
        raise EsciReviewError(
            f"Expected {expected_case_count} selected cases, found {len(selected.cases)}"
        )
    split_counts = Counter(case.split for case in selected.cases)
    expected_train = (expected_case_count + 1) // 2
    expected_test = expected_case_count // 2
    if split_counts != {"train": expected_train, "test": expected_test}:
        raise EsciReviewError("Selected dataset does not have the required balanced split")
    case_ids = [case.case_id for case in selected.cases]
    if len(case_ids) != len(set(case_ids)):
        raise EsciReviewError("Selected dataset contains duplicate case IDs")

    source_cases = {case.case_id: case for case in source.cases}
    for case in selected.cases:
        original = source_cases.get(case.case_id)
        if original is None or original.model_dump(mode="json") != case.model_dump(mode="json"):
            raise EsciReviewError(
                f"Selected case does not exactly match the verified ESCI source: {case.case_id}"
            )

    try:
        report = json.loads(
            (artifact_path / "quality-report.json").read_text(encoding="utf-8")
        )
        records = {str(item["name"]): item for item in report["output_files"]}
        manifest = json.loads(
            (artifact_path / "source-manifest.json").read_text(encoding="utf-8")
        )
        source_commit = str(manifest["commit"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise EsciReviewError("Unable to load source validation evidence") from exc
    catalog_hash = _verify_artifact_record(artifact_path, records, "catalog.json")
    _verify_artifact_record(artifact_path, records, "golden-draft.json")
    _verify_artifact_record(artifact_path, records, "source-manifest.json")

    try:
        catalog = load_catalog(artifact_path / "catalog.json")
    except CatalogLoadError as exc:
        raise EsciReviewError("Unable to load the source catalog") from exc
    if catalog.catalog_id != selected.catalog_id or catalog.version != selected.catalog_version:
        raise EsciReviewError("Selected dataset does not reference the verified source catalog")
    product_ids = {product.product_id for product in catalog.products}
    missing_products = sorted(
        {
            expected.product_id
            for case in selected.cases
            for expected in case.expected_products
            if expected.product_id not in product_ids
        }
    )
    if missing_products:
        raise EsciReviewError("Selected cases reference products missing from the source catalog")
    if any(
        case.source_provenance.get("source_commit") != source_commit
        for case in selected.cases
    ):
        raise EsciReviewError("Selected cases do not match the pinned ESCI source commit")

    validated_cases = [
        SourceValidatedCase(
            case_id=case.case_id,
            query_id=case.query_id,
            query=case.query,
            locale=case.locale,
            split=case.split,
            expected_products=case.expected_products,
            source_provenance=case.source_provenance,
        )
        for case in selected.cases
    ]
    label_counts = Counter(
        expected.relevance.value
        for case in validated_cases
        for expected in case.expected_products
    )
    base = {
        "dataset_id": selected.version,
        "version": selected.version,
        "status": "SOURCE_VALIDATED",
        "catalog_id": selected.catalog_id,
        "catalog_version": selected.catalog_version,
        "source_manifest_id": selected.source_manifest_id,
        "source_draft_hash": selected.content_hash,
        "source_catalog_hash": catalog_hash,
        "validation_evidence": {
            "validation_method": "exact-source-match-and-artifact-checksums-v1",
            "human_reviewed": False,
            "case_count": len(validated_cases),
            "split_counts": dict(sorted(split_counts.items())),
            "label_counts": dict(sorted(label_counts.items())),
            "source_commit": source_commit,
            "all_cases_exact_source_matches": True,
            "all_product_references_valid": True,
        },
        "cases": [case.model_dump(mode="json") for case in validated_cases],
    }
    published = SourceValidatedDataset.model_validate(
        {**base, "content_hash": _canonical_hash(base)}
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(published.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise EsciReviewError("Unable to publish source-validated dataset") from exc
    return published
