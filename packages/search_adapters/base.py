from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from packages.evaluation_engine.models import SearchRequest, SearchResponse


class AdapterCapabilityLevel(StrEnum):
    BASIC = "basic"
    TRACE = "trace"


class AdapterErrorCode(StrEnum):
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"


class AdapterCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: AdapterCapabilityLevel
    interpreted_query: bool = False
    applied_filters: bool = False
    retrieval_candidates: bool = False
    filtered_candidates: bool = False
    scores: bool = True


class SearchAdapterError(RuntimeError):
    def __init__(
        self,
        code: AdapterErrorCode,
        provider: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.provider = provider
        self.retryable = retryable


@runtime_checkable
class SearchAdapter(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def capabilities(self) -> AdapterCapabilities: ...

    async def search(self, request: SearchRequest) -> SearchResponse: ...
