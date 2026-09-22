from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

SENSITIVE_FRAGMENTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)


class TraceSpanRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"


class TracePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    run_id: str
    case_id: str
    name: str = "evaluation-case"
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[TraceSpanRecord] = Field(default_factory=list)


class TraceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    trace_url: str | None = None


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(fragment in str(key).casefold() for fragment in SENSITIVE_FRAGMENTS)
                else redact_sensitive(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


class TraceSession(Protocol):
    def record_span(
        self,
        name: str,
        *,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "ok",
    ) -> None: ...

    def finish(
        self,
        *,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceReference | None: ...


class TraceProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def start_case(
        self,
        *,
        run_id: str,
        case_id: str,
        query: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSession: ...
