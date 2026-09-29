from app import metrics
from app.metrics import percentile


def test_percentile_basic() -> None:
    assert percentile([100, 200, 300, 400], 50) >= 100


def test_snapshot_exposes_retrieval_success_rate(monkeypatch) -> None:
    monkeypatch.setattr(metrics, "RETRIEVAL_RESULTS", [True, True, False])

    assert metrics.snapshot()["retrieval_success_rate"] == 66.67
