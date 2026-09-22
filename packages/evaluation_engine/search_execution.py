from packages.evaluation_engine.models import SearchRequest, SearchResponse
from packages.search_adapters.base import SearchAdapter


async def execute_search(
    adapter: SearchAdapter,
    request: SearchRequest,
) -> SearchResponse:
    """Execute search only through the provider-agnostic adapter boundary."""
    return await adapter.search(request)
