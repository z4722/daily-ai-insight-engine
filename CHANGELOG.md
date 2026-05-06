# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog.

## [Unreleased]

### Added
- Added `docs/REQUIREMENTS_TRACEABILITY.md` to map each requirement to implementation evidence.
- Added `docs/MAINTENANCE_LOG.md` as an operational maintenance ledger and runbook.
- Added explicit structured extraction batching via `--extract-batch-size`.
- Added online LLM extraction chain with selectable `--extract-mode` (`rule|hybrid|llm`).
- Added extraction engine counters in run quality metrics: `llm_batches` and `rule_batches`.
- Added `src/daily_update.py` to support automated daily refresh + snapshot history + previous-run comparison.
- Added generated comparison artifacts: `outputs/daily_comparison.md` and `outputs/daily_comparison.json`.
- Added `docs/ENTERPRISE_DOC_BENCHMARK.md` with public big-tech documentation standard benchmarking and project checklist.

### Changed
- Improved dashboard to full-English UI by default with EN preset.
- Added `Export Filtered CSV` action in the visualization dashboard.
- Upgraded data pipeline with source taxonomy, relevance scoring, and diversity quota controls.
- Expanded topic/policy dictionaries and fallback tag inference to reduce `no_topic`.

### Fixed
- Improved collection logs for better filtering reason visibility (`skipped_non_ai / skipped_noise / skipped_low_relevance`).
- Strengthened smoke test assertions for schema and source diversity checks.
- Added campus-news noise heuristic to reduce false-positive AI items in aggregator feeds.

## [1.1.0] - 2026-05-06

### Added
- Added product-grade schema fields: `source_type`, `source_weight`, `source_region`, `ai_relevance_score`, `ai_relevance_reason`.
- Added mixed-source configuration across aggregator/media/official/research/social channels.
- Added interactive dashboard redesign with dynamic filtering/sorting and KPI animations.

### Changed
- Migrated scoring logic to use configurable source weights.
- Enhanced report sections with data quality snapshot and source-type distribution.

### Fixed
- Added schema validation counters and quality metrics in `run_log.json`.

## [1.0.0] - 2026-05-06

### Added
- Initial MVP pipeline: ingest, clean, deduplicate, structured extraction, analysis, report generation, and visualization.
- Added fallback dataset support to guarantee minimum output sample size.
- Added `pipeline.log` and `run_log.json` for runtime traceability.
