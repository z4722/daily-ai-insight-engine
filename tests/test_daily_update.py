from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import daily_update  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content, encoding="utf-8")


class DailyUpdateCoreTest(unittest.TestCase):
    def test_counter_delta(self) -> None:
        curr = {"a": 3, "b": 1}
        prev = {"a": 1, "c": 2}
        result = daily_update.counter_delta(curr, prev)
        table = {row["key"]: row for row in result}
        self.assertEqual(table["a"]["delta"], 2)
        self.assertEqual(table["b"]["delta"], 1)
        self.assertEqual(table["c"]["delta"], -2)

    def test_event_diff(self) -> None:
        curr = [{"id": "1", "title": "A", "source": "S"}, {"id": "2", "title": "B", "source": "S"}]
        prev = [{"id": "2", "title": "B", "source": "S"}, {"id": "3", "title": "C", "source": "S"}]
        result = daily_update.event_diff(curr, prev)
        self.assertEqual(result["unchanged_count"], 1)
        self.assertEqual(len(result["new_events"]), 1)
        self.assertEqual(len(result["removed_events"]), 1)
        self.assertEqual(result["new_events"][0]["id"], "1")
        self.assertEqual(result["removed_events"][0]["id"], "3")

    def test_story_churn(self) -> None:
        curr = [{"id": "1"}, {"id": "2"}]
        prev = [{"id": "2"}, {"id": "3"}]
        churn = daily_update.story_churn(curr, prev)
        self.assertEqual(churn["new_story_count"], 1)
        self.assertEqual(churn["removed_story_count"], 1)
        self.assertEqual(churn["common_story_count"], 1)

    def test_compare_snapshots_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            prev = base / "prev"
            curr = base / "curr"
            prev.mkdir(parents=True, exist_ok=True)
            curr.mkdir(parents=True, exist_ok=True)

            prev_run = {
                "counts": {"raw": 20, "structured": 20, "hot": 5},
                "quality": {
                    "low_confidence": 1,
                    "no_topic": 2,
                    "schema_error_count": 0,
                    "source_diversity_count": 5,
                },
                "dataset_profile": {
                    "source_distribution": {"A": 10, "B": 10},
                    "source_type_distribution": {"media": 10, "social": 10},
                    "language_distribution": {"en": 15, "zh": 5},
                },
            }
            curr_run = {
                "counts": {"raw": 22, "structured": 22, "hot": 5},
                "quality": {
                    "low_confidence": 0,
                    "no_topic": 1,
                    "schema_error_count": 0,
                    "source_diversity_count": 6,
                },
                "dataset_profile": {
                    "source_distribution": {"A": 11, "B": 9, "C": 2},
                    "source_type_distribution": {"media": 11, "social": 9, "official": 2},
                    "language_distribution": {"en": 16, "zh": 6},
                },
            }
            prev_report = {
                "trend_summary": {
                    "topics": {"Research": 8, "Policy": 2},
                    "event_types": {"Release": 4},
                    "sentiments": {"neu": 10},
                    "risks": {"Safety": 1},
                },
                "top_events": [{"id": "e1", "title": "old", "source": "A", "impact_score": 90, "hot_score": 80}],
            }
            curr_report = {
                "trend_summary": {
                    "topics": {"Research": 9, "Policy": 3},
                    "event_types": {"Release": 5},
                    "sentiments": {"neu": 11},
                    "risks": {"Safety": 2},
                },
                "top_events": [{"id": "e2", "title": "new", "source": "B", "impact_score": 92, "hot_score": 81}],
            }
            prev_rows = [{"id": "s1"}, {"id": "s2"}]
            curr_rows = [{"id": "s2"}, {"id": "s3"}]

            write_json(prev / "run_log.json", prev_run)
            write_json(curr / "run_log.json", curr_run)
            write_json(prev / "daily_report.json", prev_report)
            write_json(curr / "daily_report.json", curr_report)
            write_jsonl(prev / "structured_news.jsonl", prev_rows)
            write_jsonl(curr / "structured_news.jsonl", curr_rows)

            comparison = daily_update.compare_snapshots(curr, prev)
            self.assertEqual(comparison["counts"]["delta"]["raw"], 2)
            self.assertEqual(comparison["quality_delta"]["low_confidence_delta"], -1)
            self.assertEqual(comparison["story_churn"]["new_story_count"], 1)

            md = daily_update.to_markdown(comparison)
            self.assertIn("# Daily Comparison Report", md)
            self.assertIn("## 1) Volume Delta", md)
            self.assertIn("## 5) Topic Delta", md)


if __name__ == "__main__":
    unittest.main()
