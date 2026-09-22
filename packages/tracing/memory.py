from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from packages.tracing.base import (
    TracePayload,
    TraceReference,
    TraceSession,
    TraceSpanRecord,
    redact_sensitive,
)


class BufferedTraceSession:
    def __init__(
        self,
        payload: TracePayload,
        publish: Callable[[TracePayload], None],
        trace_url: str | None,
    ) -> None:
        self.payload = payload
        self._publish = publish
        self._trace_url = trace_url
        self._finished = False

    def record_span(
        self,
        name: str,
        *,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "ok",
    ) -> None:
        if self._finished:
            return
        self.payload.spans.append(
            TraceSpanRecord(
                name=name,
                input_data=redact_sensitive(input_data or {}),
                output_data=redact_sensitive(output_data or {}),
                metadata=redact_sensitive(metadata or {}),
                status=status,
            )
        )

    def finish(
        self,
        *,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceReference | None:
        if not self._finished:
            self.payload.output_data = redact_sensitive(output_data or {})
            self.payload.metadata.update(redact_sensitive(metadata or {}))
            self._publish(self.payload)
            self._finished = True
        return TraceReference(
            trace_id=self.payload.trace_id,
            trace_url=self._trace_url,
        )


class InMemoryTraceProvider:
    def __init__(self) -> None:
        self.traces: list[TracePayload] = []

    @property
    def provider_name(self) -> str:
        return "memory"

    def start_case(
        self,
        *,
        run_id: str,
        case_id: str,
        query: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSession:
        trace_id = uuid5(
            NAMESPACE_URL,
            f"shopfilter:{run_id}:{case_id}",
        ).hex
        payload = TracePayload(
            trace_id=trace_id,
            run_id=run_id,
            case_id=case_id,
            input_data=redact_sensitive({"query": query}),
            metadata=redact_sensitive(metadata or {}),
        )
        return BufferedTraceSession(payload, self.traces.append, None)
