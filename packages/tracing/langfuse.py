from __future__ import annotations

import base64
import json
import os
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

from packages.tracing.base import TracePayload, TraceSession, redact_sensitive
from packages.tracing.memory import BufferedTraceSession


def _string_attribute(key: str, value: Any) -> dict[str, Any]:
    return {
        "key": key,
        "value": {
            "stringValue": json.dumps(value, sort_keys=True, separators=(",", ":"))
        },
    }


class LangfuseIngestionClient:
    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str,
        project_id: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        parsed = urlparse(host)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Langfuse host must use HTTPS except for local development")
        self._public_key = public_key
        self._secret_key = secret_key
        self.host = host.rstrip("/")
        self.project_id = project_id
        self.timeout_seconds = timeout_seconds

    def publish(self, payload: TracePayload) -> None:
        start_ns = time.time_ns()
        root_span_id = uuid5(
            NAMESPACE_URL,
            f"{payload.trace_id}:evaluation-case",
        ).hex[:16]
        spans: list[dict[str, Any]] = [
            {
                "traceId": payload.trace_id,
                "spanId": root_span_id,
                "name": payload.name,
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(start_ns + 10_000_000),
                "attributes": [
                    _string_attribute("langfuse.trace.name", payload.name),
                    _string_attribute(
                        "langfuse.observation.input",
                        payload.input_data,
                    ),
                    _string_attribute(
                        "langfuse.observation.output",
                        payload.output_data,
                    ),
                    _string_attribute("shopfilter.run_id", payload.run_id),
                    _string_attribute("shopfilter.case_id", payload.case_id),
                    _string_attribute("shopfilter.metadata", payload.metadata),
                ],
            }
        ]
        for index, span in enumerate(payload.spans, start=1):
            span_start = start_ns + index * 1_000_000
            span_id = uuid5(
                NAMESPACE_URL,
                f"{payload.trace_id}:{index}:{span.name}",
            ).hex[:16]
            spans.append(
                {
                    "traceId": payload.trace_id,
                    "spanId": span_id,
                    "parentSpanId": root_span_id,
                    "name": span.name,
                    "startTimeUnixNano": str(span_start),
                    "endTimeUnixNano": str(span_start + 500_000),
                    "attributes": [
                        _string_attribute(
                            "langfuse.observation.input",
                            span.input_data,
                        ),
                        _string_attribute(
                            "langfuse.observation.output",
                            span.output_data,
                        ),
                        _string_attribute("shopfilter.status", span.status),
                        _string_attribute("shopfilter.metadata", span.metadata),
                    ],
                }
            )
        body = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            _string_attribute("service.name", "shopfilter-eval")
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": "shopfilter-eval",
                                "version": "tracing-v2",
                            },
                            "spans": spans,
                        }
                    ],
                }
            ]
        }
        credentials = base64.b64encode(
            f"{self._public_key}:{self._secret_key}".encode()
        ).decode()
        request = Request(
            f"{self.host}/api/public/otel/v1/traces",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "x-langfuse-ingestion-version": "4",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            response.read()


class LangfuseTraceProvider:
    def __init__(self, client: LangfuseIngestionClient) -> None:
        self.client = client
        self.last_error: str | None = None

    @property
    def provider_name(self) -> str:
        return "langfuse"

    def _publish_fail_open(self, payload: TracePayload) -> None:
        try:
            self.client.publish(payload)
        except (OSError, ValueError) as exc:
            self.last_error = type(exc).__name__

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
        trace_url = (
            f"{self.client.host}/project/{self.client.project_id}/traces/{trace_id}"
            if self.client.project_id
            else None
        )
        return BufferedTraceSession(
            payload,
            self._publish_fail_open,
            trace_url,
        )


def langfuse_provider_from_env() -> LangfuseTraceProvider:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv(
        "LANGFUSE_BASE_URL",
        os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    project_id = os.getenv("LANGFUSE_PROJECT_ID")
    if not public_key or not secret_key:
        raise ValueError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required"
        )
    return LangfuseTraceProvider(
        LangfuseIngestionClient(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            project_id=project_id,
        )
    )
