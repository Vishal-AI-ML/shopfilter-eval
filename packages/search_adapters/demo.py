from __future__ import annotations

from typing import Protocol

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.models import SearchRequest, SearchResponse
from packages.search_adapters.base import (
    AdapterCapabilities,
    AdapterCapabilityLevel,
    AdapterErrorCode,
    SearchAdapterError,
)


class DemoSearchBackend(Protocol):
    def search(self, request: SearchRequest) -> SearchResponse: ...


class DemoSearchAdapter:
    def __init__(self, engine: DemoSearchBackend | DemoSearchEngine) -> None:
        self._engine = engine
        self._capabilities = AdapterCapabilities(
            level=AdapterCapabilityLevel.TRACE,
            interpreted_query=True,
            applied_filters=True,
            retrieval_candidates=True,
            filtered_candidates=True,
            scores=True,
        )

    @property
    def provider_name(self) -> str:
        return "shopfilter-demo"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities

    async def search(self, request: SearchRequest) -> SearchResponse:
        try:
            response = self._engine.search(request)
        except TimeoutError as exc:
            raise SearchAdapterError(
                AdapterErrorCode.TIMEOUT,
                self.provider_name,
                "Demo search timed out",
                retryable=True,
            ) from exc
        except (RuntimeError, TypeError, ValueError) as exc:
            raise SearchAdapterError(
                AdapterErrorCode.PROVIDER_ERROR,
                self.provider_name,
                "Demo search provider failed",
                retryable=False,
            ) from exc

        if response.provider != self.provider_name:
            raise SearchAdapterError(
                AdapterErrorCode.INVALID_RESPONSE,
                self.provider_name,
                "Provider identity did not match adapter contract",
                retryable=False,
            )
        return response
