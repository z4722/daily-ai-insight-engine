# Maintenance Log

This file tracks operational maintenance notes for Daily AI Insight Engine.

## 2026-05-06

### Maintenance Actions
- Enabled multi-source strategy across six channels (aggregator/media/official/research/social).
- Added AI relevance gate and noise filtering in collection stage.
- Added source diversity quota (`min_per_source`) to prevent single-source dominance.
- Added extraction batching (`extract_batch_size`) for explicit staged processing and easier troubleshooting.
- Upgraded dashboard to full-English default and added CSV export for filtered results.
- Enabled online LLM extraction chain (`--extract-mode hybrid|llm`) with batch-level fallback to rules.
- Added extraction engine observability in `run_log.json`: `quality.llm_batches` and `quality.rule_batches`.
- Expanded topic dictionary and fallback inference for governance/cooperation signals.
- Added campus-news noise heuristic to reduce false-positive AI items from aggregator sources.
- Added `src/daily_update.py` for one-command daily refresh + snapshot archive + previous-day comparison.
- Added auto-generated comparison outputs: `outputs/daily_comparison.md` and `outputs/daily_comparison.json`.
- Added enterprise doc benchmark file `docs/ENTERPRISE_DOC_BENCHMARK.md` to align writing quality with major vendor doc standards.
- Added CI workflow for compile checks + offline unit tests.
- Added repository-level code style baseline (`.editorconfig`, `pyproject.toml`).
- Added UTF-8 console reconfiguration in CLI entrypoints for mixed-language readability.

### Health Snapshot
- Last verified run produced 20 valid records.
- Schema validation errors: 0.
- Source diversity count: 6.
- Low-confidence records are tracked in `run_log.json -> quality.low_confidence`.
- `no_topic` is tracked in `run_log.json -> quality.no_topic` and latest rule-mode verification reached `0`.

### Operational Checklist
1. Run pipeline:
   - `python src/main.py --max-items 20 --per-source-limit 8 --min-required 10 --min-relevance-score 2 --min-per-source 2 --extract-batch-size 5 --log-level INFO`
   - or `python src/daily_update.py --max-items 20 --extract-mode hybrid --log-level INFO`
2. Verify outputs exist and are non-empty:
   - `outputs/daily_report.md`
   - `outputs/daily_report.json`
   - `outputs/daily_comparison.md` (if previous snapshot exists)
   - `outputs/daily_comparison.json` (if previous snapshot exists)
   - `outputs/visualization.html`
   - `outputs/run_log.json`
   - `outputs/pipeline.log`
3. Run smoke test:
   - `python src/smoke_test.py`
4. Review data quality indicators in `run_log.json`:
   - `low_confidence`
   - `no_topic`
   - `schema_error_count`
   - `source_diversity_count`
   - `llm_batches`
   - `rule_batches`

### Known Risks / Follow-up
- Chinese text may look garbled in some terminal code pages; UTF-8 file content remains intact.
- `no_topic` can fluctuate with daily source changes; continue expanding topic and policy dictionaries if it rises again.
- Optional next step: add semantic clustering for near-duplicate cross-source stories.
