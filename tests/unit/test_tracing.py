import pytest

from packages.tracing import (
    InMemoryTraceProvider,
    LangfuseIngestionClient,
    LangfuseTraceProvider,
    NoOpTraceProvider,
    TracePayload,
    redact_sensitive,
)


def test_redaction_removes_nested_sensitive_values() -> None:
    value = {
        "query": "shoes",
        "authorization": "Bearer secret",
        "nested": {"api_key": "key", "safe": "visible"},
        "items": [{"password": "password"}],
    }
    assert redact_sensitive(value) == {
        "query": "shoes",
        "authorization": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]", "safe": "visible"},
        "items": [{"password": "[REDACTED]"}],
    }


def test_noop_provider_returns_no_trace_reference() -> None:
    session = NoOpTraceProvider().start_case(
        run_id="run-1",
        case_id="case-1",
        query="shoes",
    )
    session.record_span("retrieval", output_data={"ids": ["p-1"]})
    assert session.finish(output_data={"passed": True}) is None


def test_memory_provider_records_redacted_spans_with_otlp_trace_id() -> None:
    provider = InMemoryTraceProvider()
    session = provider.start_case(
        run_id="run-1",
        case_id="case-1",
        query="shoes",
        metadata={"secret": "hidden"},
    )
    session.record_span(
        "search-adapter",
        input_data={"api_key": "hidden"},
        output_data={"provider": "demo"},
    )
    reference = session.finish(output_data={"passed": True})

    assert reference is not None
    assert len(reference.trace_id) == 32
    assert "-" not in reference.trace_id
    assert len(provider.traces) == 1
    trace = provider.traces[0]
    assert trace.metadata["secret"] == "[REDACTED]"
    assert trace.spans[0].input_data["api_key"] == "[REDACTED]"


def test_langfuse_delivery_failure_is_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LangfuseIngestionClient(
        public_key="public",
        secret_key="secret",
        host="http://localhost:3000",
        project_id="project-test",
    )

    def fail_publish(payload: TracePayload) -> None:
        del payload
        raise OSError("offline")

    monkeypatch.setattr(client, "publish", fail_publish)
    provider = LangfuseTraceProvider(client)
    session = provider.start_case(
        run_id="run-1",
        case_id="case-1",
        query="shoes",
    )
    session.record_span("retrieval")
    reference = session.finish(output_data={"passed": True})

    assert reference is not None
    assert reference.trace_url is not None
    assert "/project/project-test/traces/" in reference.trace_url
    assert provider.last_error == "OSError"


def test_langfuse_rejects_insecure_remote_host() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        LangfuseIngestionClient(
            public_key="public",
            secret_key="secret",
            host="http://example.com",
        )
