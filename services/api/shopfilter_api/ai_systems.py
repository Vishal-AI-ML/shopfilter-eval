from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class AISystemType(StrEnum):
    LEXICAL_SEARCH = "LEXICAL_SEARCH"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    HYBRID_SEARCH = "HYBRID_SEARCH"
    RAG_ASSISTANT = "RAG_ASSISTANT"
    EXTERNAL_SEARCH_API = "EXTERNAL_SEARCH_API"
    EXTERNAL_ASSISTANT_API = "EXTERNAL_ASSISTANT_API"


class AISystemStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AISystemVersionStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class AISystemCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_understanding: bool = False
    lexical_retrieval: bool = False
    semantic_retrieval: bool = False
    hybrid_retrieval: bool = False
    reranking: bool = False
    generation: bool = False
    citations: bool = False
    tool_calling: bool = False
    conversation_state: bool = False
    traces: bool = False


def legacy_search_capabilities() -> dict[str, bool]:
    return AISystemCapabilities(lexical_retrieval=True).model_dump()


def canonical_ai_system_version_hash(
    *,
    version: str,
    configuration: dict[str, Any],
    capabilities: dict[str, Any],
) -> str:
    payload = {
        "capabilities": capabilities,
        "configuration": configuration,
        "version": version,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
