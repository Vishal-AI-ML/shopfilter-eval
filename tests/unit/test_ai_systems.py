from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.api.shopfilter_api.ai_systems import (
    AISystemCapabilities,
    canonical_ai_system_version_hash,
    legacy_search_capabilities,
)


def test_canonical_version_hash_is_order_independent_and_sha256() -> None:
    first = canonical_ai_system_version_hash(
        version="v1",
        configuration={"top_k": 10, "fusion": {"semantic": 0.6, "lexical": 0.4}},
        capabilities={"generation": True, "citations": True},
    )
    second = canonical_ai_system_version_hash(
        version="v1",
        configuration={"fusion": {"lexical": 0.4, "semantic": 0.6}, "top_k": 10},
        capabilities={"citations": True, "generation": True},
    )
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def test_capabilities_are_typed_immutable_and_reject_unknown_flags() -> None:
    capabilities = AISystemCapabilities(
        semantic_retrieval=True,
        generation=True,
        citations=True,
    )
    assert capabilities.semantic_retrieval is True
    with pytest.raises(ValidationError):
        AISystemCapabilities.model_validate({"unknown_capability": True})
    with pytest.raises(ValidationError):
        capabilities.generation = False


def test_legacy_search_capabilities_advertise_lexical_retrieval() -> None:
    capabilities = legacy_search_capabilities()
    assert capabilities["lexical_retrieval"] is True
    assert capabilities["generation"] is False
