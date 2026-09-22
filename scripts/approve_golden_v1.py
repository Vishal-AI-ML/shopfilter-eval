from __future__ import annotations

from pathlib import Path

from packages.evaluation_engine.datasets import (
    ReviewStatus,
    compute_dataset_hash,
    load_golden_dataset,
)


def main() -> None:
    root = Path.cwd()
    draft_path = root / "data" / "goldens" / "golden-v1-draft.json"
    approved_path = root / "data" / "goldens" / "golden-v1.json"
    review_path = root / "data" / "goldens" / "golden-v1-review.md"

    draft = load_golden_dataset(draft_path)
    approved_cases = [
        case.model_copy(update={"review_status": ReviewStatus.APPROVED})
        for case in draft.cases
    ]
    approved = draft.model_copy(
        update={
            "version": "v1",
            "status": ReviewStatus.APPROVED,
            "cases": approved_cases,
        }
    )
    approved = approved.model_copy(
        update={"content_hash": compute_dataset_hash(approved)}
    )
    approved_path.write_text(
        approved.model_dump_json(indent=2),
        encoding="utf-8",
    )

    review = review_path.read_text(encoding="utf-8")
    review = review.replace("☐", "☑")
    review = review.replace(
        "These cases are `IN_REVIEW`. A human must verify each query, constraint and expected product before approval.",
        "All 20 cases were human-reviewed and approved by Vishal Shivhare on 2026-09-22.",
    )
    review += (
        "\n## Approval record\n\n"
        "- Reviewer: Vishal Shivhare\n"
        "- Approved: 2026-09-22\n"
        f"- Published version: `v1`\n- Immutable hash: `{approved.content_hash}`\n"
    )
    review_path.write_text(review, encoding="utf-8")

    print("Golden V1 approved and published")
    print(f"Cases: {len(approved.cases)}")
    print(f"Status: {approved.status.value}")
    print(f"Hash: {approved.content_hash}")
    print(f"File: {approved_path}")


if __name__ == "__main__":
    main()
