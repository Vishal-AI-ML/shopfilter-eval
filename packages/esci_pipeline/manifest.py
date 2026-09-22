
from __future__ import annotations

import json
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)


class ManifestError(ValueError):
    """Raised when an ESCI source manifest is invalid."""


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceFile(StrictFrozenModel):
    name: str = Field(min_length=1)
    url: HttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def reject_paths(cls, value: str) -> str:
        if Path(value).name != value:
            raise ValueError("source file name must not contain a path")
        return value


class EsciSourceManifest(StrictFrozenModel):
    manifest_id: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1)
    repository: HttpUrl
    commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    license: str = Field(min_length=1)
    locale: str = "us"
    version_flag: str = "small_version"
    files: tuple[SourceFile, ...]

    @field_validator("files")
    @classmethod
    def require_unique_files(cls, files: tuple[SourceFile, ...]) -> tuple[SourceFile, ...]:
        names = [item.name for item in files]
        if len(names) != len(set(names)):
            raise ValueError("source file names must be unique")
        required = {
            "shopping_queries_dataset_examples.parquet",
            "shopping_queries_dataset_products.parquet",
        }
        if set(names) != required:
            raise ValueError("manifest must contain the official examples and products Parquet files")
        return files


def load_source_manifest(path: str | Path) -> EsciSourceManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return EsciSourceManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ManifestError(f"Unable to load ESCI manifest: {manifest_path}") from exc
