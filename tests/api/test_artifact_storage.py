from __future__ import annotations

import pytest

from services.api.shopfilter_api.artifact_storage import content_addressed_run_key


def test_content_addressed_run_key_is_tenant_and_project_scoped() -> None:
    key = content_addressed_run_key(
        organization_id="org-1",
        project_id="project-1",
        sha256="a" * 64,
    )
    assert key == (
        "organizations/org-1/projects/project-1/runs/"
        f"{'a' * 64}.json"
    )


def test_content_addressed_run_key_rejects_invalid_digest() -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        content_addressed_run_key(
            organization_id="org-1",
            project_id="project-1",
            sha256="not-a-sha256",
        )
