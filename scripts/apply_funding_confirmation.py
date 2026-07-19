#!/usr/bin/env python3
"""Apply funding confirmation to the published regime narrative without changing scores."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from funding_confirmation import assess_confirmation, load_modifier

ROOT = Path(__file__).resolve().parents[1]
LATEST_PATH = ROOT / "data" / "latest.json"
HISTORY_PATH = ROOT / "data" / "history.json"


def apply_overlay(
    latest: dict[str, Any],
    modifier: dict[str, Any],
) -> dict[str, Any]:
    closest_code = str(latest.get("closest_regime", {}).get("code", ""))
    market_stress = float(latest.get("scores", {}).get("stress", 0) or 0)
    core_confidence = str(latest.get("core_confidence") or latest.get("confidence") or "Medium")
    assessment = assess_confirmation(
        modifier,
        closest_code=closest_code,
        market_stress=market_stress,
        core_confidence=core_confidence,
    )

    latest["core_confidence"] = core_confidence
    latest["confidence"] = assessment["adjusted_confidence"]
    latest["funding_confirmation"] = assessment

    interpretation = latest.setdefault("interpretation", {})
    plain = str(interpretation.get("plain_english", "")).strip()
    if assessment["summary"] and assessment["summary"] not in plain:
        interpretation["plain_english"] = f"{plain} {assessment['summary']}".strip()

    watch = list(interpretation.get("watch_next", []))
    funding_watch = (
        "Watch whether hyperscaler funding stress moves above 51 and whether issuer-level "
        "credit spreads or FCF revisions confirm the market signal."
    )
    if funding_watch not in watch:
        watch.append(funding_watch)
    interpretation["watch_next"] = watch

    why = list(interpretation.get("why", []))
    signals = assessment.get("signals", {})
    funding_why = (
        f"Funding confirmation is {assessment['status'].lower()}: hyperscaler score "
        f"{signals.get('hyperscaler_funding_score')}, neocloud score "
        f"{signals.get('neocloud_financing_score')}."
    )
    if funding_why not in why:
        why.append(funding_why)
    interpretation["why"] = why

    divergences = list(latest.get("divergence_warnings", []))
    existing_types = {row.get("type") for row in divergences if isinstance(row, dict)}
    for warning in assessment.get("warnings", []):
        if warning.get("type") not in existing_types:
            divergences.append(warning)
            existing_types.add(warning.get("type"))
    latest["divergence_warnings"] = divergences

    market_read = str(latest.get("market_read", "")).strip()
    modifier_read = assessment["summary"]
    if modifier_read and modifier_read not in market_read:
        latest["market_read"] = f"{market_read} {modifier_read}".strip()
    return latest


def update_history(history_path: Path, latest: dict[str, Any]) -> None:
    if not history_path.exists():
        return
    try:
        history = json.loads(history_path.read_text())
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(history, list):
        return
    latest_date = latest.get("date")
    for row in reversed(history):
        if isinstance(row, dict) and row.get("date") == latest_date:
            row["core_confidence"] = latest.get("core_confidence")
            row["confidence"] = latest.get("confidence")
            row["funding_confirmation_status"] = latest.get("funding_confirmation", {}).get("status")
            break
    history_path.write_text(json.dumps(history, indent=2) + "\n")


def run(
    latest_path: Path = LATEST_PATH,
    history_path: Path = HISTORY_PATH,
) -> dict[str, Any]:
    latest = json.loads(latest_path.read_text())
    modifier = load_modifier()
    updated = apply_overlay(latest, modifier)
    latest_path.write_text(json.dumps(updated, indent=2) + "\n")
    update_history(history_path, updated)
    return updated


def self_test() -> None:
    latest = {
        "date": "2026-07-17",
        "regime": "Mixed / Transition",
        "closest_regime": {"code": "C", "name": "Hardware Late-Cycle Squeeze"},
        "confidence": "Medium",
        "market_read": "Market stress is high.",
        "scores": {"stress": 90.8},
        "interpretation": {"plain_english": "Late-cycle squeeze.", "why": [], "watch_next": []},
        "divergence_warnings": [],
    }
    modifier = {
        "as_of": "2099-01-01T00:00:00+00:00",
        "sync_status": "ok",
        "hyperscaler_funding": {"score": 43, "coverage_ratio": 0.65, "status": "WATCH"},
        "neocloud_financing": {"score": 77, "status": "CREDIT STRESS CONFIRMED"},
        "market_plumbing": {"score": 50, "status": "WATCH"},
    }
    updated = apply_overlay(latest, modifier)
    assert updated["scores"]["stress"] == 90.8
    assert updated["regime"] == "Mixed / Transition"
    assert updated["funding_confirmation"]["status"] == "PARTIAL"
    assert updated["confidence"] == "Medium"
    assert any(row["type"] == "Two_Speed_Funding_Stress" for row in updated["divergence_warnings"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("funding overlay self-test passed")
    else:
        updated = run()
        print(
            "applied funding confirmation: "
            f"{updated.get('funding_confirmation', {}).get('status')}"
        )


if __name__ == "__main__":
    main()
