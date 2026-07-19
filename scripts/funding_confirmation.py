#!/usr/bin/env python3
"""Sync and interpret AI-infrastructure funding confirmation signals."""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "funding_confirmation.json"
DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/davetwchiu/"
    "ai-infrastructure-stress-cockpit/main/data/regime_modifier.json"
)
CONFIDENCE_LEVELS = ["Low", "Medium", "High"]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _score_label(score: float | None) -> str:
    if score is None:
        return "UNMONITORED"
    if score >= 71:
        return "CREDIT STRESS CONFIRMED"
    if score >= 51:
        return "STRESS"
    if score >= 26:
        return "WATCH"
    return "NORMAL"


def _shift_confidence(confidence: str, amount: int) -> str:
    try:
        index = CONFIDENCE_LEVELS.index(confidence)
    except ValueError:
        index = 1
    return CONFIDENCE_LEVELS[max(0, min(len(CONFIDENCE_LEVELS) - 1, index + amount))]


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_modifier(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a stable compact schema and ignore unknown producer fields."""
    hyperscaler = payload.get("hyperscaler_funding", {})
    neocloud = payload.get("neocloud_financing", {})
    plumbing = payload.get("market_plumbing", {})
    return {
        "schema_version": int(payload.get("schema_version", 1)),
        "as_of": payload.get("as_of"),
        "source_repo": payload.get(
            "source_repo", "davetwchiu/ai-infrastructure-stress-cockpit"
        ),
        "hyperscaler_funding": {
            "score": _number(hyperscaler.get("score")),
            "status": hyperscaler.get("status") or _score_label(_number(hyperscaler.get("score"))),
            "coverage_ratio": _number(hyperscaler.get("coverage_ratio")),
            "data_status": hyperscaler.get("data_status", "unknown"),
        },
        "neocloud_financing": {
            "score": _number(neocloud.get("score")),
            "status": neocloud.get("status") or _score_label(_number(neocloud.get("score"))),
            "data_status": neocloud.get("data_status", "unknown"),
        },
        "market_plumbing": {
            "score": _number(plumbing.get("score")),
            "status": plumbing.get("status") or _score_label(_number(plumbing.get("score"))),
            "data_status": plumbing.get("data_status", "unknown"),
        },
        "source_summary": payload.get(
            "source_summary",
            "Funding and market-plumbing summary from the AI Infrastructure Stress Cockpit.",
        ),
    }


def sync_modifier(
    source_url: str = DEFAULT_SOURCE_URL,
    output_path: Path = OUTPUT_PATH,
    opener=urllib.request.urlopen,
) -> dict[str, Any]:
    """Fetch the producer file; preserve the last good observation on failure."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        request = urllib.request.Request(source_url, headers={"User-Agent": "AI-CAPEX-Regime-Dashboard/1.0"})
        with opener(request, timeout=25) as response:
            payload = json.load(response)
        normalized = normalize_modifier(payload)
        if not normalized.get("as_of"):
            raise ValueError("source payload has no as_of timestamp")
        normalized.update({"sync_status": "ok", "synced_at": now, "source_url": source_url})
    except Exception as exc:
        if output_path.exists():
            normalized = normalize_modifier(json.loads(output_path.read_text()))
            normalized.update({
                "sync_status": "stale_fallback",
                "synced_at": now,
                "source_url": source_url,
                "sync_error": str(exc),
            })
        else:
            normalized = {
                "schema_version": 1,
                "as_of": None,
                "source_repo": "davetwchiu/ai-infrastructure-stress-cockpit",
                "hyperscaler_funding": {"score": None, "status": "UNMONITORED", "coverage_ratio": 0, "data_status": "failed"},
                "neocloud_financing": {"score": None, "status": "UNMONITORED", "data_status": "failed"},
                "market_plumbing": {"score": None, "status": "UNMONITORED", "data_status": "failed"},
                "source_summary": "Funding confirmation source unavailable.",
                "sync_status": "failed",
                "synced_at": now,
                "source_url": source_url,
                "sync_error": str(exc),
            }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, indent=2) + "\n")
    return normalized


def load_modifier(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
        return normalize_modifier(payload) | {
            key: value
            for key, value in payload.items()
            if key in {"sync_status", "synced_at", "source_url", "sync_error"}
        }
    except (OSError, json.JSONDecodeError, TypeError):
        return normalize_modifier({}) | {"sync_status": "failed"}


def assess_confirmation(
    modifier: dict[str, Any],
    closest_code: str,
    market_stress: float,
    core_confidence: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply a transparent confirmation overlay without changing regime scores."""
    now = now or datetime.now(timezone.utc)
    hyperscaler = modifier.get("hyperscaler_funding", {})
    neocloud = modifier.get("neocloud_financing", {})
    plumbing = modifier.get("market_plumbing", {})
    hs_score = _number(hyperscaler.get("score"))
    neo_score = _number(neocloud.get("score"))
    plumbing_score = _number(plumbing.get("score"))
    coverage = _number(hyperscaler.get("coverage_ratio")) or 0.0
    source_time = _parse_datetime(modifier.get("as_of"))
    age_days = (now - source_time).total_seconds() / 86400 if source_time else None
    stale = age_days is None or age_days > 4 or modifier.get("sync_status") == "failed"

    if closest_code in {"C", "D"}:
        if hs_score is not None and neo_score is not None and hs_score >= 51 and neo_score >= 51:
            status = "CONFIRMED"
        elif (hs_score is not None and hs_score >= 26) or (neo_score is not None and neo_score >= 51):
            status = "PARTIAL"
        elif hs_score is not None and neo_score is not None:
            status = "NOT CONFIRMED"
        else:
            status = "UNMONITORED"
    else:
        if (hs_score is not None and hs_score >= 51) or (neo_score is not None and neo_score >= 71):
            status = "CONTRADICTED"
        elif hs_score is not None and neo_score is not None and hs_score < 26 and neo_score < 51:
            status = "SUPPORTIVE"
        elif hs_score is not None or neo_score is not None:
            status = "PARTIAL"
        else:
            status = "UNMONITORED"

    adjusted = core_confidence
    confidence_action = "unchanged"
    if not stale:
        if status == "CONFIRMED" and coverage >= 0.65 and closest_code in {"C", "D"}:
            adjusted = _shift_confidence(core_confidence, 1)
            confidence_action = "raised"
        elif status in {"NOT CONFIRMED", "CONTRADICTED"}:
            adjusted = _shift_confidence(core_confidence, -1)
            confidence_action = "lowered"

    warnings: list[dict[str, str]] = []
    if stale:
        warnings.append({
            "type": "Funding_Data_Stale",
            "severity": "medium",
            "message": "Funding confirmation data is stale or unavailable; the market regime remains price-led.",
        })
    if market_stress >= 60 and neo_score is not None and neo_score >= 71 and (hs_score is None or hs_score < 51):
        warnings.append({
            "type": "Two_Speed_Funding_Stress",
            "severity": "high",
            "message": "Neocloud financing stress is elevated, while broad hyperscaler funding stress is not yet confirmed.",
        })
    elif market_stress >= 60 and (hs_score is not None and hs_score < 26) and (neo_score is not None and neo_score < 51):
        warnings.append({
            "type": "Market_Stress_Unconfirmed_By_Credit",
            "severity": "medium",
            "message": "High market stress lacks funding confirmation and may still reflect valuation or liquidity pressure.",
        })
    if hs_score is not None and hs_score >= 51 and market_stress < 60:
        warnings.append({
            "type": "Funding_Stress_Ahead_Of_Market",
            "severity": "high",
            "message": "Hyperscaler funding stress is rising before the market-implied stress score has confirmed it.",
        })

    if status == "CONFIRMED":
        summary = "Funding data confirms the market-implied late-cycle or bubble-fear regime."
    elif status == "PARTIAL":
        summary = "Funding confirmation is partial: fringe borrowers are weaker, but broad hyperscaler credit has not fully deteriorated."
    elif status == "NOT CONFIRMED":
        summary = "Funding data does not confirm the price-led stress regime."
    elif status == "CONTRADICTED":
        summary = "Funding stress contradicts an otherwise constructive market regime."
    elif status == "SUPPORTIVE":
        summary = "Funding conditions support the constructive market regime."
    else:
        summary = "Funding confirmation is unavailable."

    return {
        "status": status,
        "core_confidence": core_confidence,
        "adjusted_confidence": adjusted,
        "confidence_action": confidence_action,
        "is_stale": stale,
        "age_days": round(age_days, 1) if age_days is not None else None,
        "source_as_of": modifier.get("as_of"),
        "sync_status": modifier.get("sync_status", "unknown"),
        "summary": summary,
        "signals": {
            "hyperscaler_funding_score": hs_score,
            "hyperscaler_status": hyperscaler.get("status", _score_label(hs_score)),
            "hyperscaler_coverage_ratio": coverage,
            "neocloud_financing_score": neo_score,
            "neocloud_status": neocloud.get("status", _score_label(neo_score)),
            "market_plumbing_score": plumbing_score,
            "market_plumbing_status": plumbing.get("status", _score_label(plumbing_score)),
        },
        "warnings": warnings,
        "methodology": "Diagnostic overlay only; it does not alter Demand, Bottleneck, Rotation, Stress, Breadth, or the hard regime classification.",
    }


def self_test() -> None:
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    modifier = normalize_modifier({
        "as_of": "2026-07-19T07:00:00+00:00",
        "hyperscaler_funding": {"score": 43, "coverage_ratio": 0.65, "data_status": "partial"},
        "neocloud_financing": {"score": 77},
        "market_plumbing": {"score": 50},
    }) | {"sync_status": "ok"}
    result = assess_confirmation(modifier, "C", 91, "Medium", now=now)
    assert result["status"] == "PARTIAL"
    assert result["adjusted_confidence"] == "Medium"
    assert any(row["type"] == "Two_Speed_Funding_Stress" for row in result["warnings"])

    confirmed = normalize_modifier({
        "as_of": "2026-07-19T07:00:00+00:00",
        "hyperscaler_funding": {"score": 60, "coverage_ratio": 0.8},
        "neocloud_financing": {"score": 75},
    }) | {"sync_status": "ok"}
    result = assess_confirmation(confirmed, "D", 80, "Medium", now=now)
    assert result["status"] == "CONFIRMED"
    assert result["adjusted_confidence"] == "High"

    constructive = normalize_modifier({
        "as_of": "2026-07-19T07:00:00+00:00",
        "hyperscaler_funding": {"score": 55, "coverage_ratio": 0.8},
        "neocloud_financing": {"score": 45},
    }) | {"sync_status": "ok"}
    result = assess_confirmation(constructive, "A", 35, "High", now=now)
    assert result["status"] == "CONTRADICTED"
    assert result["adjusted_confidence"] == "Medium"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--source-url", default=os.getenv("FUNDING_CONFIRMATION_URL", DEFAULT_SOURCE_URL))
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("funding confirmation self-test passed")
    if args.sync:
        result = sync_modifier(args.source_url)
        print(f"funding confirmation sync: {result.get('sync_status')}")
    if not args.self_test and not args.sync:
        parser.print_help()


if __name__ == "__main__":
    main()
