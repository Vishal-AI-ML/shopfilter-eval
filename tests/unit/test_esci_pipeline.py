from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any, Self

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from packages.esci_pipeline.download import (
    DownloadError,
    download_source_file,
    sha256_file,
)
from packages.esci_pipeline.manifest import (
    EsciSourceManifest,
    SourceFile,
    load_source_manifest,
)
from packages.esci_pipeline.prepare import (
    EsciPreparationError,
    PreparationConfig,
    prepare_esci_subset,
    verify_processed_artifacts,
)

ROOT = Path(__file__).parents[2]
OFFICIAL_MANIFEST = ROOT / "data" / "manifests" / "esci-amazon-science-2024-10-07.json"


class _Response(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _source(name: str, payload: bytes) -> SourceFile:
    return SourceFile(
        name=name,
        url="https://example.test/" + name,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def test_official_manifest_pins_commit_lfs_hashes_and_sizes() -> None:
    manifest = load_source_manifest(OFFICIAL_MANIFEST)
    assert manifest.commit == "7916cdf6ab75a462e77f20ab40428a10923998d5"
    assert manifest.license == "Apache-2.0"
    assert {item.name: (item.sha256, item.size_bytes) for item in manifest.files} == {
        "shopping_queries_dataset_examples.parquet": (
            "4a735b693b4a424a6fc67f5be6e4c811495c488bbf66d02a602d308b2744263a",
            51286808,
        ),
        "shopping_queries_dataset_products.parquet": (
            "25124442d064d64b26f74082d6fa09438d679efc0c183cf28d19064a2b65a265",
            1108857465,
        ),
    }


def test_download_is_atomic_and_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"verified parquet fixture"
    source = _source("fixture.parquet", payload)
    monkeypatch.setattr(
        "packages.esci_pipeline.download.urlopen",
        lambda *_args, **_kwargs: _Response(payload),
    )
    destination = download_source_file(source, tmp_path)
    assert destination.read_bytes() == payload
    assert sha256_file(destination) == source.sha256
    assert not (tmp_path / ".fixture.parquet.part").exists()


def test_download_rejects_mismatch_without_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source("fixture.parquet", b"expected")
    monkeypatch.setattr(
        "packages.esci_pipeline.download.urlopen",
        lambda *_args, **_kwargs: _Response(b"wrong"),
    )
    with pytest.raises(DownloadError, match="failed verification"):
        download_source_file(source, tmp_path)
    assert not (tmp_path / "fixture.parquet").exists()
    assert not (tmp_path / ".fixture.parquet.part").exists()


def test_existing_valid_download_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"existing"
    source = _source("fixture.parquet", payload)
    (tmp_path / source.name).write_bytes(payload)

    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network must not be used")

    monkeypatch.setattr("packages.esci_pipeline.download.urlopen", fail_network)
    assert download_source_file(source, tmp_path).read_bytes() == payload


def _write_parquet_fixtures(raw_directory: Path) -> EsciSourceManifest:
    raw_directory.mkdir(parents=True)
    examples_path = raw_directory / "shopping_queries_dataset_examples.parquet"
    products_path = raw_directory / "shopping_queries_dataset_products.parquet"
    examples: dict[str, list[Any]] = {
        "example_id": [1, 2, 3, 4, 5, 6],
        "query": ["red shoes", "red shoes", "phone case", "phone case", "zapatos", "easy"],
        "query_id": [10, 10, 20, 20, 30, 40],
        "product_id": ["p1", "p2", "p3", "p4", "p5", "p6"],
        "product_locale": ["us", "us", "us", "us", "es", "us"],
        "esci_label": ["E", "I", "S", "C", "E", "E"],
        "small_version": [1, 1, 1, 1, 1, 0],
        "large_version": [1, 1, 1, 1, 1, 1],
        "split": ["train", "train", "test", "test", "train", "train"],
    }
    products: dict[str, list[Any]] = {
        "product_id": ["p1", "p2", "p3", "p4", "p5", "p6"],
        "product_title": ["Red Shoe A", "Red Shoe B", "Case A", "Case B", "Zapato", "Easy"],
        "product_description": ["A", "B", "C", None, "E", "F"],
        "product_bullet_point": [None, None, None, "bullet", None, None],
        "product_brand": ["A", "B", "C", "D", "E", "F"],
        "product_color": ["red", "red", "black", "blue", "rojo", None],
        "product_locale": ["us", "us", "us", "us", "es", "us"],
    }
    pq.write_table(pa.table(examples), examples_path)
    pq.write_table(pa.table(products), products_path)
    files = []
    for path in (examples_path, products_path):
        files.append(
            SourceFile(
                name=path.name,
                url="https://example.test/" + path.name,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return EsciSourceManifest(
        manifest_id="fixture-manifest",
        dataset_name="ESCI fixture",
        repository="https://example.test/repository",
        commit="1" * 40,
        license="Apache-2.0",
        locale="us",
        version_flag="small_version",
        files=tuple(files),
    )


def test_preparation_filters_normalizes_and_marks_draft_unapproved(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    manifest = _write_parquet_fixtures(raw_root / "fixture-manifest")
    destination = prepare_esci_subset(
        manifest,
        raw_root,
        tmp_path / "processed",
        PreparationConfig(version="fixture-v1", target_products=3, seed=7),
    )
    report = verify_processed_artifacts(destination)
    assert report.requested_product_count == 3
    assert report.actual_product_count == 4
    assert report.query_count == 2
    assert report.split_counts == {"test": 1, "train": 1}
    assert report.label_counts == {"C": 1, "E": 1, "I": 1, "S": 1}

    catalog = json.loads((destination / "catalog.json").read_text(encoding="utf-8"))
    assert {product["product_id"] for product in catalog["products"]} == {"p1", "p2", "p3", "p4"}
    first = catalog["products"][0]
    assert first["category"] == "unknown"
    assert first["price"] == "0.00"
    assert first["field_provenance"]["price"].startswith("synthetic_placeholder")
    assert first["source_metadata"]["source_commit"] == "1" * 40

    draft = json.loads((destination / "golden-draft.json").read_text(encoding="utf-8"))
    assert draft["status"] == "IN_REVIEW"
    assert all(case["review_status"] == "IN_REVIEW" for case in draft["cases"])


def test_preparation_is_reproducible_and_immutable(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    manifest = _write_parquet_fixtures(raw_root / "fixture-manifest")
    config = PreparationConfig(version="fixture-v1", target_products=3, seed=7)
    first = prepare_esci_subset(manifest, raw_root, tmp_path / "out-a", config)
    second = prepare_esci_subset(manifest, raw_root, tmp_path / "out-b", config)
    for name in ("catalog.json", "golden-draft.json", "source-manifest.json", "quality-report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    with pytest.raises(FileExistsError, match="immutable"):
        prepare_esci_subset(manifest, raw_root, tmp_path / "out-a", config)


def test_processed_verification_detects_tampering(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    manifest = _write_parquet_fixtures(raw_root / "fixture-manifest")
    destination = prepare_esci_subset(
        manifest,
        raw_root,
        tmp_path / "processed",
        PreparationConfig(version="fixture-v1", target_products=1),
    )
    with (destination / "catalog.json").open("a", encoding="utf-8") as stream:
        stream.write("tampered")
    with pytest.raises(EsciPreparationError, match="failed verification"):
        verify_processed_artifacts(destination)
