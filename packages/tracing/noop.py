from __future__ import annotations

from typing import Any

from packages.tracing.base import TraceReference, TraceSession


class NoOpTraceSession:
    def record_span(
        self,
        name: str,
        *,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "ok",
    ) -> None:
        del name, input_data, output_data, metadata, status

    def finish(
        self,
        *,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceReference | None:
        del output_data, metadata
        return None


class NoOpTraceProvider:
    @property
    def provider_name(self) -> str:
        return "noop"

    def start_case(
        self,
        *,
        run_id: str,
        case_id: str,
        query: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSession:
        del run_id, case_id, query, metadata
        return NoOpTraceSession()
