from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import percentile


DEFAULT_LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.svg"


def load_recent_records(path: Path, minutes: int = 60) -> list[dict]:
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        records.append({**record, "_timestamp": timestamp})

    if not records:
        return []
    end = max(record["_timestamp"] for record in records)
    start = end - timedelta(minutes=minutes)
    return [record for record in records if record["_timestamp"] >= start]


def build_metrics(records: list[dict]) -> dict:
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    latencies = [int(record["latency_ms"]) for record in responses if "latency_ms" in record]
    ttfts = [int(record["ttft_ms"]) for record in responses if "ttft_ms" in record]
    costs = [float(record["cost_usd"]) for record in responses if "cost_usd" in record]
    quality = [float(record["quality_score"]) for record in responses if "quality_score" in record]
    retrievals = [
        bool(record["tool_success"])
        for record in records
        if record.get("tool_name") == "retrieval" and record.get("tool_success") is not None
    ]
    error_types: dict[str, int] = defaultdict(int)
    for record in failures:
        error_types[str(record.get("error_type", "unknown"))] += 1

    active_request_minutes = len(
        {
            record["_timestamp"].replace(second=0, microsecond=0)
            for record in requests
        }
    )

    return {
        "request_count": len(requests),
        "rate_per_minute": len(requests) / max(1, active_request_minutes),
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "latency_p99": percentile(latencies, 99),
        "ttft_p95": percentile(ttfts, 95),
        "error_rate": 100 * len(failures) / len(requests) if requests else 0.0,
        "error_types": dict(error_types),
        "retrieval_success": 100 * sum(retrievals) / len(retrievals) if retrievals else 0.0,
        "total_cost": sum(costs),
        "tokens_in": sum(int(record.get("tokens_in", 0)) for record in responses),
        "tokens_out": sum(int(record.get("tokens_out", 0)) for record in responses),
        "quality_avg": mean(quality) if quality else 0.0,
    }


def panel(x: int, y: int, title: str, lines: list[str], threshold: str, healthy: bool) -> str:
    status = "PASS" if healthy else "ALERT"
    status_color = "#15803d" if healthy else "#b91c1c"
    line_nodes = "".join(
        f'<text x="{x + 30}" y="{y + 100 + index * 42}" class="metric">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="670" height="220" rx="16" class="card"/>
      <text x="{x + 30}" y="{y + 45}" class="panel-title">{escape(title)}</text>
      <rect x="{x + 555}" y="{y + 20}" width="85" height="32" rx="16" fill="{status_color}"/>
      <text x="{x + 597}" y="{y + 42}" class="status">{status}</text>
      {line_nodes}
      <text x="{x + 30}" y="{y + 198}" class="threshold">Threshold: {escape(threshold)}</text>
    </g>
    """


def render_svg(metrics: dict, record_count: int) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    panels = [
        panel(
            40,
            150,
            "1. Latency percentiles and TTFT",
            [
                f"P50 {metrics['latency_p50']:.0f} ms  |  P95 {metrics['latency_p95']:.0f} ms",
                f"P99 {metrics['latency_p99']:.0f} ms  |  TTFT P95 {metrics['ttft_p95']:.0f} ms",
            ],
            "P95 <= 3000 ms",
            metrics["latency_p95"] <= 3000,
        ),
        panel(
            730,
            150,
            "2. Request traffic",
            [
                f"Requests {metrics['request_count']}",
                f"Active rate {metrics['rate_per_minute']:.2f} requests/min",
            ],
            "rate >= 1 request/min",
            metrics["rate_per_minute"] >= 1,
        ),
        panel(
            40,
            390,
            "3. Errors and retrieval success",
            [
                f"Error rate {metrics['error_rate']:.2f}%",
                f"Retrieval success {metrics['retrieval_success']:.2f}%",
            ],
            "errors <= 2%; retrieval >= 90%",
            metrics["error_rate"] <= 2 and metrics["retrieval_success"] >= 90,
        ),
        panel(
            730,
            390,
            "4. Cost over time",
            [f"Total ${metrics['total_cost']:.6f}", "Window 60 minutes"],
            "total <= $2.50",
            metrics["total_cost"] <= 2.5,
        ),
        panel(
            40,
            630,
            "5. Input and output tokens",
            [
                f"Input {metrics['tokens_in']:,} tokens",
                f"Output {metrics['tokens_out']:,} tokens",
            ],
            "combined <= 50,000 tokens",
            metrics["tokens_in"] + metrics["tokens_out"] <= 50000,
        ),
        panel(
            730,
            630,
            "6. Quality proxy",
            [f"Average {metrics['quality_avg']:.2f} / 1.00", "Heuristic quality score"],
            "mean >= 0.75",
            metrics["quality_avg"] >= 0.75,
        ),
    ]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1440" viewBox="0 0 1440 1440">
  <style>
    .background {{ fill: #f4f7fb; }}
    .card {{ fill: #ffffff; stroke: #d9e2ef; stroke-width: 1.5; }}
    .title {{ font: 700 30px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #172033; }}
    .subtitle {{ font: 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #667085; }}
    .panel-title {{ font: 700 19px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #172033; }}
    .metric {{ font: 600 21px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #253858; }}
    .threshold {{ font: 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #667085; }}
    .status {{ font: 700 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: white; text-anchor: middle; }}
  </style>
  <rect width="1440" height="900" class="background"/>
  <text x="40" y="55" class="title">K4-L3A Day 13 — Monitoring &amp; LLMOps</text>
  <text x="40" y="88" class="subtitle">Source: data/logs.jsonl · Time range: last 60 minutes · Refresh: 30 seconds · {record_count} log records</text>
  <text x="40" y="115" class="subtitle">Generated: {generated_at}</text>
  {''.join(panels)}
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the six-panel CP2 dashboard as SVG")
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    if not args.logs.exists():
        print(f"Error: {args.logs} not found")
        return 1
    records = load_recent_records(args.logs)
    if not records:
        print("Error: no valid records in the last 60 minutes")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(build_metrics(records), len(records)), encoding="utf-8")
    print(f"Dashboard written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
