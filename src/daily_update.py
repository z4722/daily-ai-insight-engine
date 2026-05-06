from __future__ import annotations

import argparse
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import main

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
HISTORY_DIR = OUTPUT_DIR / "history"

LOGGER = logging.getLogger("daily_update")


@dataclass
class Snapshot:
    name: str
    path: Path
    created_at: datetime


def setup_logger(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    LOGGER.setLevel(level)
    LOGGER.propagate = False
    if LOGGER.handlers:
        for handler in list(LOGGER.handlers):
            LOGGER.removeHandler(handler)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(fmt)
    LOGGER.addHandler(stream)


def ensure_history_dir(history_dir: Path) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("History directory ready: %s", history_dir)


def parse_iso_or_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def list_snapshots(history_dir: Path) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    for child in history_dir.iterdir():
        if not child.is_dir():
            continue
        meta_path = child / "snapshot_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                created = parse_iso_or_now(meta.get("created_at"))
            except Exception as exc:
                LOGGER.warning("Failed to parse snapshot meta: %s error=%s", meta_path, exc)
                created = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
        else:
            created = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
        snapshots.append(Snapshot(name=child.name, path=child, created_at=created))
    snapshots.sort(key=lambda s: s.created_at)
    LOGGER.info("Detected snapshots: %d", len(snapshots))
    return snapshots


def pick_previous_snapshot(history_dir: Path) -> Snapshot | None:
    snapshots = list_snapshots(history_dir)
    if not snapshots:
        LOGGER.info("No previous snapshot found")
        return None
    prev = snapshots[-1]
    LOGGER.info("Previous snapshot selected: %s", prev.path)
    return prev


def build_snapshot_name(custom_name: str | None = None) -> str:
    if custom_name:
        return custom_name
    now_local = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{now_local}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        LOGGER.warning("Artifact missing, skip copy: %s", src)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    LOGGER.info("Copied artifact: %s -> %s", src, dst)
    return True


def create_snapshot(history_dir: Path, snapshot_name: str, run_log: dict[str, Any]) -> Path:
    snapshot_dir = history_dir / snapshot_name
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Creating snapshot: %s", snapshot_dir)

    artifacts = run_log.get("artifacts", {})
    copy_map = {
        "raw": snapshot_dir / "raw_news.jsonl",
        "structured": snapshot_dir / "structured_news.jsonl",
        "report": snapshot_dir / "daily_report.md",
        "report_json": snapshot_dir / "daily_report.json",
        "visual": snapshot_dir / "visualization.html",
        "pipeline_log": snapshot_dir / "pipeline.log",
    }

    for artifact_key, dst in copy_map.items():
        raw_path = artifacts.get(artifact_key)
        if not raw_path:
            LOGGER.warning("Artifact key missing in run_log: %s", artifact_key)
            continue
        copy_if_exists(Path(raw_path), dst)

    run_log_path = OUTPUT_DIR / "run_log.json"
    copy_if_exists(run_log_path, snapshot_dir / "run_log.json")

    meta = {
        "snapshot_name": snapshot_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_generated_at": run_log.get("generated_at"),
        "run_params": run_log.get("run_params", {}),
        "counts": run_log.get("counts", {}),
        "quality": run_log.get("quality", {}),
    }
    write_json(snapshot_dir / "snapshot_meta.json", meta)
    LOGGER.info("Snapshot meta written: %s", snapshot_dir / "snapshot_meta.json")
    return snapshot_dir


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        LOGGER.warning("JSONL not found: %s", path)
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except Exception as exc:
            LOGGER.warning("Failed parsing jsonl line in %s error=%s", path, exc)
    return rows


def counter_delta(curr: dict[str, int], prev: dict[str, int]) -> list[dict[str, Any]]:
    keys = set(curr.keys()) | set(prev.keys())
    diffs: list[dict[str, Any]] = []
    for key in keys:
        curr_v = int(curr.get(key, 0))
        prev_v = int(prev.get(key, 0))
        diffs.append(
            {
                "key": key,
                "current": curr_v,
                "previous": prev_v,
                "delta": curr_v - prev_v,
            }
        )
    diffs.sort(key=lambda x: (abs(x["delta"]), x["current"]), reverse=True)
    return diffs


def event_diff(curr_events: list[dict[str, Any]], prev_events: list[dict[str, Any]]) -> dict[str, Any]:
    curr_map = {row.get("id", f"curr_{idx}"): row for idx, row in enumerate(curr_events)}
    prev_map = {row.get("id", f"prev_{idx}"): row for idx, row in enumerate(prev_events)}
    curr_ids = set(curr_map.keys())
    prev_ids = set(prev_map.keys())

    new_ids = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    unchanged_ids = curr_ids & prev_ids

    new_events = [
        {
            "id": eid,
            "title": curr_map[eid].get("title", ""),
            "source": curr_map[eid].get("source", ""),
            "impact_score": curr_map[eid].get("impact_score", 0),
            "hot_score": curr_map[eid].get("hot_score", 0),
        }
        for eid in sorted(new_ids)
    ]
    removed_events = [
        {
            "id": eid,
            "title": prev_map[eid].get("title", ""),
            "source": prev_map[eid].get("source", ""),
            "impact_score": prev_map[eid].get("impact_score", 0),
            "hot_score": prev_map[eid].get("hot_score", 0),
        }
        for eid in sorted(removed_ids)
    ]
    return {
        "new_events": new_events,
        "removed_events": removed_events,
        "unchanged_count": len(unchanged_ids),
    }


def story_churn(curr_structured: list[dict[str, Any]], prev_structured: list[dict[str, Any]]) -> dict[str, int]:
    curr_ids = {row.get("id", "") for row in curr_structured if row.get("id")}
    prev_ids = {row.get("id", "") for row in prev_structured if row.get("id")}
    return {
        "new_story_count": len(curr_ids - prev_ids),
        "removed_story_count": len(prev_ids - curr_ids),
        "common_story_count": len(curr_ids & prev_ids),
    }


def compare_snapshots(curr_snapshot: Path, prev_snapshot: Path) -> dict[str, Any]:
    LOGGER.info("Comparing snapshots current=%s previous=%s", curr_snapshot, prev_snapshot)
    curr_run = read_json(curr_snapshot / "run_log.json")
    prev_run = read_json(prev_snapshot / "run_log.json")
    curr_report = read_json(curr_snapshot / "daily_report.json")
    prev_report = read_json(prev_snapshot / "daily_report.json")
    curr_structured = load_jsonl(curr_snapshot / "structured_news.jsonl")
    prev_structured = load_jsonl(prev_snapshot / "structured_news.jsonl")

    curr_counts = curr_run.get("counts", {})
    prev_counts = prev_run.get("counts", {})
    curr_quality = curr_run.get("quality", {})
    prev_quality = prev_run.get("quality", {})

    curr_profile = curr_run.get("dataset_profile", {})
    prev_profile = prev_run.get("dataset_profile", {})

    curr_trend = curr_report.get("trend_summary", {})
    prev_trend = prev_report.get("trend_summary", {})

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_snapshot": str(curr_snapshot),
        "previous_snapshot": str(prev_snapshot),
        "counts": {
            "current": curr_counts,
            "previous": prev_counts,
            "delta": {
                "raw": int(curr_counts.get("raw", 0)) - int(prev_counts.get("raw", 0)),
                "structured": int(curr_counts.get("structured", 0)) - int(prev_counts.get("structured", 0)),
                "hot": int(curr_counts.get("hot", 0)) - int(prev_counts.get("hot", 0)),
            },
        },
        "quality_delta": {
            "low_confidence_delta": int(curr_quality.get("low_confidence", 0))
            - int(prev_quality.get("low_confidence", 0)),
            "no_topic_delta": int(curr_quality.get("no_topic", 0)) - int(prev_quality.get("no_topic", 0)),
            "schema_error_delta": int(curr_quality.get("schema_error_count", 0))
            - int(prev_quality.get("schema_error_count", 0)),
            "source_diversity_delta": int(curr_quality.get("source_diversity_count", 0))
            - int(prev_quality.get("source_diversity_count", 0)),
        },
        "distribution_delta": {
            "source_distribution": counter_delta(
                curr_profile.get("source_distribution", {}), prev_profile.get("source_distribution", {})
            ),
            "source_type_distribution": counter_delta(
                curr_profile.get("source_type_distribution", {}),
                prev_profile.get("source_type_distribution", {}),
            ),
            "language_distribution": counter_delta(
                curr_profile.get("language_distribution", {}),
                prev_profile.get("language_distribution", {}),
            ),
        },
        "trend_delta": {
            "topics": counter_delta(curr_trend.get("topics", {}), prev_trend.get("topics", {})),
            "event_types": counter_delta(curr_trend.get("event_types", {}), prev_trend.get("event_types", {})),
            "sentiments": counter_delta(curr_trend.get("sentiments", {}), prev_trend.get("sentiments", {})),
            "risks": counter_delta(curr_trend.get("risks", {}), prev_trend.get("risks", {})),
        },
        "top_event_diff": event_diff(curr_report.get("top_events", []), prev_report.get("top_events", [])),
        "story_churn": story_churn(curr_structured, prev_structured),
    }
    return comparison


def to_markdown(comparison: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Daily Comparison Report")
    lines.append("")
    lines.append(f"- Generated At (UTC): {comparison.get('generated_at', '')}")
    lines.append(f"- Current Snapshot: `{comparison.get('current_snapshot', '')}`")
    lines.append(f"- Previous Snapshot: `{comparison.get('previous_snapshot', '')}`")
    lines.append("")

    count_delta = comparison.get("counts", {}).get("delta", {})
    lines.append("## 1) Volume Delta")
    lines.append(f"- raw: {count_delta.get('raw', 0):+d}")
    lines.append(f"- structured: {count_delta.get('structured', 0):+d}")
    lines.append(f"- hot: {count_delta.get('hot', 0):+d}")
    lines.append("")

    quality_delta = comparison.get("quality_delta", {})
    lines.append("## 2) Quality Delta")
    lines.append(f"- low_confidence: {quality_delta.get('low_confidence_delta', 0):+d}")
    lines.append(f"- no_topic: {quality_delta.get('no_topic_delta', 0):+d}")
    lines.append(f"- schema_error_count: {quality_delta.get('schema_error_delta', 0):+d}")
    lines.append(f"- source_diversity_count: {quality_delta.get('source_diversity_delta', 0):+d}")
    lines.append("")

    lines.append("## 3) Story Churn")
    churn = comparison.get("story_churn", {})
    lines.append(f"- new_story_count: {churn.get('new_story_count', 0)}")
    lines.append(f"- removed_story_count: {churn.get('removed_story_count', 0)}")
    lines.append(f"- common_story_count: {churn.get('common_story_count', 0)}")
    lines.append("")

    lines.append("## 4) Top Event Changes")
    event_change = comparison.get("top_event_diff", {})
    new_events = event_change.get("new_events", [])
    removed_events = event_change.get("removed_events", [])
    lines.append(f"- unchanged_top_events: {event_change.get('unchanged_count', 0)}")
    if new_events:
        lines.append("- new_top_events:")
        for row in new_events[:5]:
            lines.append(
                f"  - {row.get('title', '')} | source={row.get('source', '')} | impact={row.get('impact_score', 0)}"
            )
    else:
        lines.append("- new_top_events: none")
    if removed_events:
        lines.append("- removed_top_events:")
        for row in removed_events[:5]:
            lines.append(
                f"  - {row.get('title', '')} | source={row.get('source', '')} | impact={row.get('impact_score', 0)}"
            )
    else:
        lines.append("- removed_top_events: none")
    lines.append("")

    lines.append("## 5) Topic Delta (Top 8 by |delta|)")
    topic_delta = comparison.get("trend_delta", {}).get("topics", [])
    if not topic_delta:
        lines.append("- none")
    else:
        for row in topic_delta[:8]:
            lines.append(
                f"- {row.get('key', '')}: delta={row.get('delta', 0):+d} (current={row.get('current', 0)}, previous={row.get('previous', 0)})"
            )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily updater: run pipeline, archive outputs, compare with previous")
    parser.add_argument("--max-items", type=int, default=20, help="Maximum news items in final dataset")
    parser.add_argument("--per-source-limit", type=int, default=8, help="Per source fetch cap")
    parser.add_argument("--min-required", type=int, default=10, help="Minimum items required to continue")
    parser.add_argument("--min-relevance-score", type=int, default=2, help="Minimum AI relevance score (0-10)")
    parser.add_argument("--min-per-source", type=int, default=2, help="Diversity quota per source before global fill")
    parser.add_argument("--extract-batch-size", type=int, default=5, help="Structured extraction batch size")
    parser.add_argument("--extract-mode", type=str, default="hybrid", choices=["rule", "hybrid", "llm"], help="Extraction engine mode")
    parser.add_argument("--llm-model", type=str, default=main.DEFAULT_LLM_MODEL, help="LLM model for online extraction")
    parser.add_argument("--llm-timeout-sec", type=int, default=45, help="Timeout seconds per LLM batch request")
    parser.add_argument("--history-dir", type=str, default=str(HISTORY_DIR), help="Snapshot history directory")
    parser.add_argument("--snapshot-name", type=str, default="", help="Custom snapshot name")
    parser.add_argument("--no-compare", action="store_true", help="Disable snapshot comparison step")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logger level")
    return parser.parse_args()


def main_entry() -> None:
    main.configure_console_encoding()
    args = parse_args()
    setup_logger(args.log_level)
    history_dir = Path(args.history_dir)
    ensure_history_dir(history_dir)

    prev_snapshot = pick_previous_snapshot(history_dir)
    LOGGER.info(
        "Starting daily update: max_items=%d extract_mode=%s history_dir=%s",
        args.max_items,
        args.extract_mode,
        history_dir,
    )
    run_log = main.run(
        max_items=args.max_items,
        per_source_limit=args.per_source_limit,
        min_required=args.min_required,
        min_relevance_score=args.min_relevance_score,
        min_per_source=args.min_per_source,
        extract_batch_size=args.extract_batch_size,
        extract_mode=args.extract_mode,
        llm_model=args.llm_model,
        llm_timeout_sec=args.llm_timeout_sec,
        log_level=args.log_level,
    )

    snapshot_name = build_snapshot_name(args.snapshot_name or None)
    curr_snapshot = create_snapshot(history_dir, snapshot_name, run_log)

    compare_written = False
    comparison_path = OUTPUT_DIR / "daily_comparison.md"
    comparison_json_path = OUTPUT_DIR / "daily_comparison.json"
    if not args.no_compare and prev_snapshot is not None:
        comparison = compare_snapshots(curr_snapshot, prev_snapshot.path)
        write_json(comparison_json_path, comparison)
        comparison_md = to_markdown(comparison)
        comparison_path.write_text(comparison_md, encoding="utf-8")
        # Keep comparison copy in snapshot for audit history.
        write_json(curr_snapshot / "daily_comparison.json", comparison)
        (curr_snapshot / "daily_comparison.md").write_text(comparison_md, encoding="utf-8")
        compare_written = True
        LOGGER.info("Comparison report written: %s", comparison_path)
    else:
        LOGGER.info("Comparison skipped: no previous snapshot or --no-compare set")

    output = {
        "snapshot": str(curr_snapshot),
        "comparison_written": compare_written,
        "comparison_md": str(comparison_path) if compare_written else "",
        "comparison_json": str(comparison_json_path) if compare_written else "",
        "run_counts": run_log.get("counts", {}),
        "run_quality": run_log.get("quality", {}),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main_entry()
