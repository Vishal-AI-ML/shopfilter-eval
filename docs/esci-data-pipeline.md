
# Amazon ESCI English-subset pipeline

Phase 13 uses the official Amazon Science Shopping Queries Dataset. The source is pinned to repository commit `7916cdf6ab75a462e77f20ab40428a10923998d5` and Apache-2.0 licensing. The tracked source manifest records the official Git LFS object SHA-256 and byte size for both Parquet files.

## Safety and evidence rules

- Raw files live under `data/raw/` and are never committed or overwritten.
- Existing raw files must match both the pinned byte size and SHA-256.
- Processed directories are immutable; a repeated version/scale path fails rather than overwrites.
- Phase 13 filters `product_locale == "us"` and the reduced `small_version == 1` source.
- Complete query groups are retained. The requested product count is a minimum, so the actual count can be slightly larger.
- ESCI supplies no category, price, currency, or availability. Compatibility values for those required catalog fields are explicit synthetic placeholders with field-level provenance. They must not be treated as Amazon facts or business data.
- Generated golden cases remain `IN_REVIEW`. ESCI labels are source judgments, not ShopFilter human approval.

## Download

The two raw files require approximately 1.2 GB, plus temporary and processed space.

```powershell
uv run shopfilter esci download
```

Downloads are streamed to `.part` files, verified, and atomically renamed. A partial or mismatched file is rejected.

## Prepare and verify the first scale

```powershell
uv run shopfilter esci prepare --target-products 1000 --version esci-en-v1
uv run shopfilter esci verify data/processed/esci-en-v1/products-1000
```

After reviewing the quality report, repeat at 5,000 products with a new version so the initial artifact remains immutable:

```powershell
uv run shopfilter esci prepare --target-products 5000 --version esci-en-v1-p5000
uv run shopfilter esci verify data/processed/esci-en-v1-p5000/products-5000
```

Do not scale to 10,000 until the 5,000-product quality report and retrieval behavior justify it.

## Outputs

Each processed directory contains:

- `catalog.json`: normalized ShopFilter catalog with source and field provenance.
- `golden-draft.json`: deterministic ESCI query/judgment cases marked `IN_REVIEW`.
- `source-manifest.json`: exact pinned source identity.
- `quality-report.json`: counts, selection method, synthetic fields, and output checksums.

A future review workflow may publish a 200-case golden dataset, but this pipeline never auto-approves cases.

## Create the 200-case review packet

After the 10,000-product artifact is verified, select a balanced deterministic review set:

```powershell
uv run shopfilter esci review-create `
  data/processed/esci-en-v1-p10000/products-10000 `
  --case-count 200 `
  --version esci-golden-v1
```

This writes an immutable JSON draft and a human-readable Markdown review packet under `data/goldens/`. Selection targets 100 train and 100 test cases, prioritizes label diversity and uses a fixed seed. Every case remains `IN_REVIEW`; this command cannot publish or approve data.

## Automated source validation

When manual review is intentionally deferred, publish the selected cases as `SOURCE_VALIDATED` rather than `HUMAN_APPROVED`:

```powershell
uv run shopfilter esci source-validate `
  data/processed/esci-en-v1-p10000/products-10000 `
  --draft data/goldens/esci-golden-v1-draft.json `
  --output data/goldens/esci-golden-v1-source-validated.json
```

The validator requires an exact match to the verified source draft, valid catalog references, pinned source commit, artifact sizes and SHA-256 checksums, 200 unique cases, and a balanced 100/100 train/test split. The published evidence explicitly records `human_reviewed: false`. It never upgrades automated validation to human approval.
