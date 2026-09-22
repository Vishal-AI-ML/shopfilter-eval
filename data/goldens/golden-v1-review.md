# Golden V1 prototype review checklist

Dataset hash: `9038646c859bc75950067d65af3bf7aedd675d917c8ef839c446826a73120e29`

> All 20 cases were human-reviewed and approved by Vishal Shivhare on 2026-09-22.

| Case | Type | Query | Expected products | Review |
|---|---|---|---|---|
| F-001 | filter | nike men's black running shoes below ₹3000 size 9 | SHOE-001 | ☑ |
| F-002 | filter | adidas women's blue sneakers under INR 2000 size 7 | SHOE-002 | ☑ |
| F-003 | filter | puma men's navy running shoes under 2500 size 9 | SHOE-031 | ☑ |
| F-004 | filter | nike women's pink boots under 1500 size 6 | SHOE-029 | ☑ |
| F-005 | filter | reebok unisex pink walking shoes under 2500 size 9 | SHOE-018 | ☑ |
| F-006 | filter | nike unisex green hoodies max 3000 size M available | CLOTH-006 | ☑ |
| F-007 | filter | samsung brown smartphone under 2000 available | ELEC-003 | ☑ |
| F-008 | filter | wildcraft grey backpack below 3000 | BAG-001 | ☑ |
| RET-001 | retrieval | running shoes | SHOE-001, SHOE-007, SHOE-013, SHOE-019, SHOE-025, SHOE-031 | ☑ |
| RET-002 | retrieval | wireless earbuds | ELEC-002, ELEC-011, ELEC-020 | ☑ |
| RET-003 | retrieval | backpacks | BAG-001, BAG-006 | ☑ |
| RET-004 | retrieval | women's dresses | CLOTH-005, CLOTH-014, CLOTH-023 | ☑ |
| RANK-001 | ranking | black running shoes | SHOE-001 | ☑ |
| RANK-002 | ranking | nike shoes | SHOE-001, SHOE-015, SHOE-008, SHOE-022, SHOE-029 | ☑ |
| RANK-003 | ranking | sony headphones | ELEC-001, ELEC-010, ELEC-019 | ☑ |
| RANK-004 | ranking | titan analog watch | WATCH-001, WATCH-009 | ☑ |
| QU-001 | query_understanding | nike men's black running shoes below ₹3000 size 9 | SHOE-001 | ☑ |
| QU-002 | query_understanding | cheapest available samsung smartphones under INR 20000 | ELEC-003 | ☑ |
| CQ-001 | catalog_quality | women's running shoes size 10 | None (negative/catalog case) | ☑ |
| CQ-002 | catalog_quality | orange running shoes | None (negative/catalog case) | ☑ |

## Approval rules

- Open every referenced product in `data/demo/catalog-v1.json`.
- Verify intent, filters, relevance label and expected rank.
- Negative cases must genuinely have no matching controlled product.
- Do not change status to `APPROVED` until all 20 boxes are reviewed.
- Any content edit requires recomputing the immutable SHA-256 hash.

## Approval record

- Reviewer: Vishal Shivhare
- Approved: 2026-09-22
- Published version: `v1`
- Immutable hash: `ef36e105bc8408b68f55065d90320e4e9e212be3d2aab43eb972469e5b45d080`
