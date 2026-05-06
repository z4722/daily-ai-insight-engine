# Requirements Traceability Matrix

This matrix checks every requirement from the task brief against current implementation status.

## A. Goal & Scope

| Requirement | Status | Evidence |
|---|---|---|
| Build an MVP that extracts structured insights from daily news and generates readable analysis + visualization | Done | `src/main.py`, `outputs/daily_report.md`, `outputs/visualization.html` |
| Support trend analysis / public-opinion monitoring / decision support | Done | `outputs/daily_report.md`, `outputs/daily_report.json` |

## B. Data Acquisition

| Requirement | Status | Evidence |
|---|---|---|
| Self-selected data sources | Done | `configs/sources.json` |
| At least 10-20 recent AI items | Done | `outputs/run_log.json -> counts.raw` |
| Mixed Chinese + English preferred | Done | `outputs/run_log.json -> dataset_profile.language_distribution` |
| Include title, body/summary, source, published time | Done | `data/raw/raw_news.jsonl` |
| Explain source selection rationale | Done | `data/raw/source_notes.md`, `docs/PROJECT_DOCUMENTATION.md` |

## C. Structured Output (Schema)

| Requirement | Status | Evidence |
|---|---|---|
| Design a structured schema | Done | `configs/schema.json` |
| Explain why fields are designed this way | Done | `docs/SCHEMA_DESIGN.md` |
| Not summary-only; must be structured extraction | Done | `data/processed/structured_news.jsonl` |

## D. Analysis Report

| Requirement | Status | Evidence |
|---|---|---|
| Top 3-5 key AI events | Done | `outputs/daily_report.md` |
| Deep summary for key events (background + impact) | Done | `outputs/daily_report.md` |
| Trend judgment (tech/app/policy/capital) | Done | `outputs/daily_report.md` |
| Risk or opportunity hints | Done | `outputs/daily_report.md` |
| Logical support, not empty claims | Done | `evidence` fields in structured data + report references |

## E. Visualization

| Requirement | Status | Evidence |
|---|---|---|
| Include visualization output | Done | `outputs/visualization.html` |
| Clear information delivery | Done | Interactive dashboard with KPI/filter/sort/timeline/sentiment/topic views |

## F. Constraints Compliance

| Requirement | Status | Evidence |
|---|---|---|
| No one-shot raw dump to AI for full result | Done | Staged pipeline in `src/main.py` |
| Must show processing logic (cleaning/batch/validation) | Done | cleaning + relevance filter + dedup + `extract_batch_size` + schema checks |
| No screenshot-only submission | Done | Full code/data/report/docs provided |
| Not just summary concatenation | Done | structured schema + scoring + evidence + trend stats |

Verification standard for "not summary stitching":
- Structured output must include semantic fields beyond summary:
  - `topic_tags`, `entities`, `event_type`, `risk_tags`, `opportunity_tags`, `evidence`, `impact_score`, `extract_confidence`
- Run quality log must include process metrics:
  - `no_topic`, `schema_error_count`, `llm_batches`, `rule_batches`
- Evidence paths:
  - `data/processed/structured_news.jsonl`
  - `outputs/run_log.json`
  - `outputs/pipeline.log`
  - `docs/PROJECT_DOCUMENTATION.md` section `3.2 处理逻辑审计清单`

## G. Submission Package

| Requirement | Status | Evidence |
|---|---|---|
| Code/scripts | Done | `src/` |
| Raw data files with source notes | Done | `data/raw/raw_news.jsonl`, `data/raw/source_notes.md` |
| At least one complete daily report sample | Done | `outputs/daily_report.md` |
| Documentation with source/design/AI usage/full flow | Done | `docs/PROJECT_DOCUMENTATION.md`, `docs/AI_USAGE.md`, `docs/SCHEMA_DESIGN.md` |

## H. Completeness Verdict

- Functional completeness: **Completed for MVP scope**
- Data quality maturity: **Good, with room to improve topic coverage and multilingual normalization**
- Operational readiness: **Improved with run logs, maintenance log, and changelog**

## I. Post-MVP Enhancements (Requested Follow-up)

| Requirement | Status | Evidence |
|---|---|---|
| Enable online LLM extraction path | Done | `src/main.py` (`--extract-mode`, `call_openai_extraction_batch`) |
| Keep robust fallback when no API key / API error | Done | `src/main.py` hybrid/llm fallback logs + `quality.rule_batches` |
| Reduce `no_topic` quality issue | Done | `src/main.py` expanded `TOPIC_RULES` + fallback inference + campus-noise heuristic |
| Daily auto-refresh + compare with previous day | Done | `src/daily_update.py`, `outputs/history/`, `outputs/daily_comparison.md` |
