
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.esci_pipeline.download import sha256_file
from packages.esci_pipeline.models import EsciDraftCase, EsciDraftDataset
from packages.esci_pipeline.review import (
    EsciReviewError,
    compute_draft_hash,
    create_review_packet,
    load_verified_draft,
    publish_source_validated_dataset,
    select_review_cases,
)
from packages.evaluation_engine.models import ExpectedProduct


def _case(index: int, split: str) -> EsciDraftCase:
    return EsciDraftCase(
        case_id=f"ESCI-{index:03d}",
        query_id=index,
        query=f"query {index}",
        split=split,
        expected_products=[
            ExpectedProduct(product_id=f"p-{index}-e", relevance="E"),
            ExpectedProduct(product_id=f"p-{index}-i", relevance="I"),
        ],
        source_provenance={"query": "fixture", "judgments": "fixture", "source_commit": "1" * 40},
    )


def _dataset(case_count: int = 12) -> EsciDraftDataset:
    cases = [_case(index, "train" if index % 2 == 0 else "test") for index in range(case_count)]
    base = {
        "dataset_id": "source-draft",
        "version": "source-v1",
        "status": "IN_REVIEW",
        "catalog_id": "catalog",
        "catalog_version": "v1",
        "source_manifest_id": "manifest",
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    placeholder = EsciDraftDataset.model_validate({**base, "content_hash": "0" * 64})
    return placeholder.model_copy(update={"content_hash": compute_draft_hash(placeholder)})


def test_selector_is_balanced_deterministic_and_never_auto_approves() -> None:
    source = _dataset()
    first = select_review_cases(source, case_count=10, seed=29)
    second = select_review_cases(source, case_count=10, seed=29)
    assert first == second
    assert len(first.cases) == 10
    assert sum(case.split == "train" for case in first.cases) == 5
    assert sum(case.split == "test" for case in first.cases) == 5
    assert first.status == "IN_REVIEW"
    assert all(case.review_status == "IN_REVIEW" for case in first.cases)
    assert compute_draft_hash(first) == first.content_hash


def test_selector_rejects_insufficient_split_candidates() -> None:
    source = _dataset(case_count=4)
    with pytest.raises(EsciReviewError, match="Not enough train/test"):
        select_review_cases(source, case_count=6)


def test_loader_rejects_tampered_draft(tmp_path: Path) -> None:
    source = _dataset()
    payload = source.model_dump(mode="json")
    payload["cases"][0]["query"] = "tampered"
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EsciReviewError, match="content hash"):
        load_verified_draft(path)


def test_review_packet_contains_titles_and_stays_in_review(tmp_path: Path) -> None:
    source = _dataset(case_count=4)
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "golden-draft.json").write_text(
        source.model_dump_json(indent=2), encoding="utf-8"
    )
    products = []
    for case in source.cases:
        for expected in case.expected_products:
            products.append(
                {
                    "product_id": expected.product_id,
                    "title": f"Title {expected.product_id}",
                    "category": "unknown",
                    "price": "0.00",
                    "currency": "USD",
                    "availability": "unknown",
                }
            )
    (artifact / "catalog.json").write_text(
        json.dumps({"catalog_id": "catalog", "version": "v1", "products": products}),
        encoding="utf-8",
    )
    (artifact / "quality-report.json").write_text(
        json.dumps({"output_files": [{"name": "catalog.json", "sha256": "a" * 64}]}),
        encoding="utf-8",
    )
    draft_path, review_path, selected = create_review_packet(
        artifact, tmp_path / "out", case_count=4, seed=29, version="review-v1"
    )
    assert draft_path.is_file()
    assert selected.status == "IN_REVIEW"
    markdown = review_path.read_text(encoding="utf-8")
    assert "Human Review Packet" in markdown
    assert "[ ] APPROVE  [ ] REJECT" in markdown
    assert "Title p-" in markdown
    with pytest.raises(FileExistsError, match="immutable"):
        create_review_packet(
            artifact, tmp_path / "out", case_count=4, seed=29, version="review-v1"
        )



def test_source_validation_publishes_without_claiming_human_review(tmp_path: Path) -> None:
    source = _dataset(case_count=4)
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    source_path = artifact / "golden-draft.json"
    source_path.write_text(source.model_dump_json(indent=2), encoding="utf-8")
    products = []
    for case in source.cases:
        for expected in case.expected_products:
            products.append(
                {
                    "product_id": expected.product_id,
                    "title": f"Title {expected.product_id}",
                    "category": "unknown",
                    "price": "0.00",
                    "currency": "USD",
                    "availability": "unknown",
                }
            )
    catalog_path = artifact / "catalog.json"
    catalog_path.write_text(
        json.dumps({"catalog_id": "catalog", "version": "v1", "products": products}),
        encoding="utf-8",
    )
    manifest_path = artifact / "source-manifest.json"
    manifest_path.write_text(json.dumps({"commit": "1" * 40}), encoding="utf-8")
    records = []
    for path in (catalog_path, source_path, manifest_path):
        records.append(
            {
                "name": path.name,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    (artifact / "quality-report.json").write_text(
        json.dumps({"output_files": records}), encoding="utf-8"
    )
    selected_path = tmp_path / "selected.json"
    selected_path.write_text(source.model_dump_json(indent=2), encoding="utf-8")
    output_path = tmp_path / "source-validated.json"

    published = publish_source_validated_dataset(
        selected_path,
        artifact,
        output_path,
        expected_case_count=4,
    )
    assert published.status == "SOURCE_VALIDATED"
    assert published.validation_evidence["human_reviewed"] is False
    assert published.validation_evidence["all_cases_exact_source_matches"] is True
    assert all(case.validation_status == "SOURCE_VALIDATED" for case in published.cases)
    assert output_path.is_file()
    with pytest.raises(FileExistsError, match="already exists"):
        publish_source_validated_dataset(
            selected_path,
            artifact,
            output_path,
            expected_case_count=4,
        )
