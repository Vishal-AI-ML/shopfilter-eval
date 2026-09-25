from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from services.api.shopfilter_api.catalog_import_schemas import (
    CatalogImportRequest,
    CatalogImportResponse,
)
from services.api.shopfilter_api.dependencies import DbSession, ResourceWriter
from services.api.shopfilter_api.version_persistence import (
    VersionImportError,
    import_catalog_artifact,
)

router = APIRouter(prefix="/v1/catalog-imports", tags=["catalog imports"])
MAX_CATALOG_IMPORT_BYTES = 25 * 1024 * 1024


@router.post("", response_model=CatalogImportResponse, status_code=status.HTTP_201_CREATED)
async def import_catalog(
    request: Request,
    session: DbSession,
    writer: ResourceWriter,
) -> CatalogImportResponse:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Catalog import requires JSON")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_CATALOG_IMPORT_BYTES:
                raise HTTPException(status_code=413, detail="Catalog import is too large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid content length") from exc

    raw_body = await request.body()
    if len(raw_body) > MAX_CATALOG_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Catalog import is too large")
    try:
        payload = CatalogImportRequest.model_validate(json.loads(raw_body))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid catalog import request") from exc

    artifact_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="shopfilter-catalog-import-",
            delete=False,
        ) as artifact:
            json.dump(payload.artifact, artifact, ensure_ascii=False, separators=(",", ":"))
            artifact_path = Path(artifact.name)
        summary = import_catalog_artifact(
            session,
            organization_id=writer.organization_id,
            project_id=payload.project_id,
            artifact_path=artifact_path,
        )
    except VersionImportError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        if artifact_path is not None:
            try:
                os.unlink(artifact_path)
            except FileNotFoundError:
                pass

    return CatalogImportResponse(
        resource_id=summary.resource_id,
        version_id=summary.version_id,
        external_id=summary.external_id,
        version=summary.version,
        created=summary.created,
        item_count=summary.item_count,
        content_hash=summary.content_hash,
        artifact_hash=summary.artifact_hash,
    )
