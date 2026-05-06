from __future__ import annotations

from pathlib import Path

from main import run


def smoke_test() -> None:
    result = run(
        max_items=12,
        per_source_limit=6,
        min_required=10,
        min_relevance_score=2,
        min_per_source=2,
        extract_batch_size=4,
        extract_mode="rule",
    )
    assert result["counts"]["raw"] >= 10, "raw count is below threshold"
    assert result["counts"]["structured"] == result["counts"]["raw"], "structured count mismatch"
    assert result["quality"]["schema_error_count"] == 0, "schema errors found"
    assert result["quality"]["source_diversity_count"] >= 2, "source diversity too low"

    for _, artifact in result["artifacts"].items():
        path = Path(artifact)
        assert path.exists(), f"missing artifact: {path}"
        assert path.stat().st_size > 0, f"artifact empty: {path}"

    print("SMOKE_TEST_PASS")


if __name__ == "__main__":
    smoke_test()
