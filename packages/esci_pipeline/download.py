
from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.esci_pipeline.manifest import EsciSourceManifest, SourceFile

_CHUNK_SIZE = 1024 * 1024


class DownloadError(RuntimeError):
    """Raised when an immutable ESCI source cannot be safely downloaded."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_file(path: str | Path, source: SourceFile) -> None:
    file_path = Path(path)
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        raise DownloadError(f"Missing source file: {file_path}") from exc
    if size != source.size_bytes:
        raise DownloadError(
            f"Size mismatch for {source.name}: expected {source.size_bytes}, found {size}"
        )
    actual_hash = sha256_file(file_path)
    if actual_hash != source.sha256:
        raise DownloadError(
            f"SHA-256 mismatch for {source.name}: expected {source.sha256}, found {actual_hash}"
        )


def download_source_file(
    source: SourceFile,
    destination_directory: str | Path,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> Path:
    destination = Path(destination_directory) / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_source_file(destination, source)
        return destination

    temporary = destination.with_name(f".{destination.name}.part")
    if temporary.exists():
        temporary.unlink()
    request = Request(str(source.url), headers={"User-Agent": "shopfilter-eval/0.1"})
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with urlopen(request, timeout=60) as response, temporary.open("xb") as output:
            while chunk := response.read(_CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(source.name, downloaded, source.size_bytes)
            output.flush()
            os.fsync(output.fileno())
    except (HTTPError, URLError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise DownloadError(f"Unable to download {source.name}") from exc

    if downloaded != source.size_bytes or digest.hexdigest() != source.sha256:
        temporary.unlink(missing_ok=True)
        raise DownloadError(f"Downloaded file failed verification: {source.name}")
    temporary.replace(destination)
    return destination


def download_manifest(
    manifest: EsciSourceManifest,
    raw_root: str | Path,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[Path]:
    destination = Path(raw_root) / manifest.manifest_id
    return [
        download_source_file(source, destination, on_progress=on_progress)
        for source in manifest.files
    ]
