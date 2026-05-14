from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import main as pipeline

HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = HARNESS_ROOT / "datasets" / "demo_input.jsonl"
DEFAULT_ASSERTIONS = HARNESS_ROOT / "config" / "assertions_demo.json"
DEFAULT_RUNS_DIR = HARNESS_ROOT / "runs"

INPUT_REQUIRED_FIELDS = [
    "title",
    "summary",
    "source",
    "url",
    "published_at",
    "source_type",
    "source_weight",
    "source_region",
    "ai_relevance_score",
    "ai_relevance_reason",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"JSONL line {line_no} is not an object")
        rows.append(obj)
    return rows


def normalize_input_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        missing = [k for k in INPUT_REQUIRED_FIELDS if k not in item]
        if missing:
            raise ValueError(f"Input row {idx} missing fields: {', '.join(missing)}")

        item["title"] = str(item.get("title", "")).strip()
        item["summary"] = str(item.get("summary", "")).strip()
        item["source"] = str(item.get("source", "")).strip()
        item["url"] = str(item.get("url", "")).strip()
        item["published_at"] = str(item.get("published_at", "")).strip()
        item["source_type"] = str(item.get("source_type", "unknown")).strip() or "unknown"
        item["source_region"] = str(item.get("source_region", "global")).strip() or "global"
        item["ai_relevance_reason"] = str(item.get("ai_relevance_reason", "harness_input")).strip() or "harness_input"

        try:
            item["source_weight"] = float(item.get("source_weight", 0.7))
        except Exception:
            item["source_weight"] = 0.7

        try:
            item["ai_relevance_score"] = int(float(item.get("ai_relevance_score", 0)))
        except Exception:
            item["ai_relevance_score"] = 0

        normalized.append(item)

    return normalized


def read_assertions(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_checks(result: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    counts = result["counts"]
    quality = result["quality"]
    profile = result["dataset_profile"]

    low_conf_ratio = quality["low_confidence"] / max(1, counts["structured"])

    def add_check(name: str, passed: bool, actual: Any, expected: str) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "actual": actual,
                "expected": expected,
            }
        )

    add_check(
        "input_count_range",
        cfg["min_input_items"] <= counts["input"] <= cfg["max_input_items"],
        counts["input"],
        f"between {cfg['min_input_items']} and {cfg['max_input_items']}",
    )
    add_check(
        "top_events_range",
        cfg["min_top_events"] <= counts["hot_events"] <= cfg["max_top_events"],
        counts["hot_events"],
        f"between {cfg['min_top_events']} and {cfg['max_top_events']}",
    )
    add_check(
        "schema_errors",
        quality["schema_error_count"] <= cfg["max_schema_errors"],
        quality["schema_error_count"],
        f"<= {cfg['max_schema_errors']}",
    )
    add_check(
        "no_topic",
        quality["no_topic"] <= cfg["max_no_topic"],
        quality["no_topic"],
        f"<= {cfg['max_no_topic']}",
    )
    add_check(
        "avg_confidence",
        profile["avg_confidence"] >= cfg["min_avg_confidence"],
        profile["avg_confidence"],
        f">= {cfg['min_avg_confidence']}",
    )
    add_check(
        "source_diversity",
        quality["source_diversity_count"] >= cfg["min_source_diversity"],
        quality["source_diversity_count"],
        f">= {cfg['min_source_diversity']}",
    )
    add_check(
        "low_confidence_ratio",
        low_conf_ratio <= cfg["max_low_confidence_ratio"],
        round(low_conf_ratio, 4),
        f"<= {cfg['max_low_confidence_ratio']}",
    )

    return checks


def render_harness_markdown(summary: dict[str, Any]) -> str:
    checks = summary["checks"]
    lines = [
        "# Harness Run Report",
        "",
        f"- run_id: {summary['run_id']}",
        f"- generated_at: {summary['generated_at']}",
        f"- extract_mode: {summary['run_params']['extract_mode']}",
        f"- dataset: `{summary['run_params']['dataset']}`",
        f"- all_checks_passed: {summary['all_checks_passed']}",
        "",
        "## Counts",
        f"- input: {summary['counts']['input']}",
        f"- structured: {summary['counts']['structured']}",
        f"- hot_events: {summary['counts']['hot_events']}",
        "",
        "## Quality",
        f"- low_confidence: {summary['quality']['low_confidence']}",
        f"- no_topic: {summary['quality']['no_topic']}",
        f"- schema_error_count: {summary['quality']['schema_error_count']}",
        f"- source_diversity_count: {summary['quality']['source_diversity_count']}",
        f"- llm_batches: {summary['quality']['llm_batches']}",
        f"- rule_batches: {summary['quality']['rule_batches']}",
        "",
        "## Checks",
    ]

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(
            f"- [{status}] {check['name']}: actual={check['actual']} expected={check['expected']}"
        )

    lines.extend(
        [
            "",
            "## Artifacts",
            f"- raw: `{summary['artifacts']['raw']}`",
            f"- structured: `{summary['artifacts']['structured']}`",
            f"- report_md: `{summary['artifacts']['report_md']}`",
            f"- report_json: `{summary['artifacts']['report_json']}`",
            f"- visual_html: `{summary['artifacts']['visual_html']}`",
            f"- harness_result_json: `{summary['artifacts']['harness_result_json']}`",
        ]
    )

    return "\n".join(lines)


def execute_harness(
    dataset: Path,
    assertions_cfg_path: Path,
    output_dir: Path,
    extract_mode: str,
    extract_batch_size: int,
    llm_model: str,
    llm_timeout_sec: int,
    log_level: str,
) -> tuple[dict[str, Any], Path]:
    start = time.perf_counter()

    pipeline.ensure_dirs()
    pipeline.setup_logger(log_level=log_level)

    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = normalize_input_rows(read_jsonl(dataset))
    schema = pipeline.load_schema()
    required_fields = schema.get("required", [])
    schema_version = schema.get("version", "unknown")
    prompt_template = pipeline.load_extract_prompt()

    effective_batch_size = max(1, extract_batch_size)
    structured: list[dict[str, Any]] = []
    low_confidence = 0
    no_topic = 0
    schema_error_count = 0
    llm_batches = 0
    rule_batches = 0

    for batch_start in range(0, len(raw_rows), effective_batch_size):
        batch = raw_rows[batch_start : batch_start + effective_batch_size]
        batch_structured, extractor_used = pipeline.extract_structured_batch(
            batch_rows=batch,
            extract_mode=extract_mode,
            llm_model=llm_model,
            llm_timeout_sec=llm_timeout_sec,
            prompt_template=prompt_template,
        )

        if extractor_used == "llm":
            llm_batches += 1
        else:
            rule_batches += 1

        for row in batch_structured:
            missing = pipeline.missing_required_fields(row, required_fields)
            if missing:
                schema_error_count += 1
            if float(row.get("extract_confidence", 0.0)) < 0.60:
                low_confidence += 1
            if not row.get("topic_tags"):
                no_topic += 1
            structured.append(row)

    hot_events = pipeline.top_hot_events(structured, top_n=min(5, len(structured)))
    trends = pipeline.summarize_trends(structured)
    dataset_profile = pipeline.profile_dataset(raw_rows, structured)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_path = run_dir / "raw_news.jsonl"
    structured_path = run_dir / "structured_news.jsonl"
    report_md_path = run_dir / "daily_report.md"
    report_json_path = run_dir / "daily_report.json"
    visual_path = run_dir / "visualization.html"

    pipeline.write_jsonl(raw_path, raw_rows)
    pipeline.write_jsonl(structured_path, structured)
    pipeline.render_visualization(structured, trends, visual_path)
    pipeline.render_report(structured, hot_events, trends, dataset_profile, schema_version, report_md_path)
    pipeline.render_report_json(structured, hot_events, trends, dataset_profile, schema_version, report_json_path)

    summary: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        "run_params": {
            "dataset": str(dataset.resolve()),
            "assertions_config": str(assertions_cfg_path.resolve()),
            "extract_mode": extract_mode,
            "extract_batch_size": effective_batch_size,
            "llm_model": llm_model,
            "llm_timeout_sec": llm_timeout_sec,
            "log_level": log_level.upper(),
        },
        "counts": {
            "input": len(raw_rows),
            "structured": len(structured),
            "hot_events": len(hot_events),
        },
        "quality": {
            "low_confidence": low_confidence,
            "no_topic": no_topic,
            "schema_error_count": schema_error_count,
            "source_diversity_count": len(dataset_profile.get("source_distribution", {})),
            "llm_batches": llm_batches,
            "rule_batches": rule_batches,
        },
        "dataset_profile": dataset_profile,
        "elapsed_sec": round(time.perf_counter() - start, 3),
    }

    assertions_cfg = read_assertions(assertions_cfg_path)
    checks = run_checks(summary, assertions_cfg)
    summary["checks"] = checks
    summary["all_checks_passed"] = all(item["passed"] for item in checks)

    result_json_path = run_dir / "harness_result.json"
    summary["artifacts"] = {
        "raw": str(raw_path),
        "structured": str(structured_path),
        "report_md": str(report_md_path),
        "report_json": str(report_json_path),
        "visual_html": str(visual_path),
        "harness_result_json": str(result_json_path),
    }

    result_md_path = run_dir / "harness_result.md"
    result_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    result_md_path.write_text(render_harness_markdown(summary), encoding="utf-8")

    return summary, run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal offline harness for Daily AI Insight Engine")
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET), help="JSONL dataset path")
    parser.add_argument("--assertions-config", type=str, default=str(DEFAULT_ASSERTIONS), help="Harness assertion config path")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_RUNS_DIR), help="Harness run output directory")
    parser.add_argument("--extract-mode", type=str, default="rule", choices=["rule", "hybrid", "llm"], help="Extraction mode")
    parser.add_argument("--extract-batch-size", type=int, default=4, help="Batch size for extraction")
    parser.add_argument("--llm-model", type=str, default=pipeline.DEFAULT_LLM_MODEL, help="LLM model for hybrid/llm modes")
    parser.add_argument("--llm-timeout-sec", type=int, default=45, help="Timeout seconds per LLM batch")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, run_dir = execute_harness(
        dataset=Path(args.dataset),
        assertions_cfg_path=Path(args.assertions_config),
        output_dir=Path(args.output_dir),
        extract_mode=args.extract_mode,
        extract_batch_size=args.extract_batch_size,
        llm_model=args.llm_model,
        llm_timeout_sec=args.llm_timeout_sec,
        log_level=args.log_level,
    )
    print(json.dumps({
        "all_checks_passed": summary["all_checks_passed"],
        "run_dir": str(run_dir),
        "result_json": str(Path(summary["artifacts"]["harness_result_json"])),
        "result_md": str(run_dir / "harness_result.md"),
    }, ensure_ascii=False, indent=2))

    if not summary["all_checks_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
