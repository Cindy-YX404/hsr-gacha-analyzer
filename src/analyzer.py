"""Account-level and pool-level statistical analysis."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config.gacha_rules import POOL_RULES
from src.pity import current_pool_state


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def analyze_pool(frame: pd.DataFrame, pool_type: str) -> dict[str, Any]:
    pool = frame[frame["pool_type"].eq(pool_type)]
    five = pool[pool["is_five_star"]]
    state = current_pool_state(frame, pool_type)
    rule = POOL_RULES.get(pool_type, POOL_RULES["unknown"])

    small_wins = int(five["five_star_result_type"].eq("up").sum())
    small_losses = int(five["five_star_result_type"].eq("off_banner").sum())
    guaranteed_wins = int(five["five_star_result_type"].eq("guaranteed_up").sum())
    pity_values = pd.to_numeric(five["pity_count"], errors="coerce").dropna()

    return {
        "pool_type": pool_type,
        "total_pulls": int(len(pool)),
        "five_stars": int(len(five)),
        "four_stars": int(pool["is_four_star"].sum()),
        "average_pity": float(pity_values.mean()) if not pity_values.empty else None,
        "median_pity": float(pity_values.median()) if not pity_values.empty else None,
        "earliest_pity": int(pity_values.min()) if not pity_values.empty else None,
        "latest_pity": int(pity_values.max()) if not pity_values.empty else None,
        "off_banner_count": small_losses,
        "small_pity_wins": small_wins,
        "guaranteed_wins": guaranteed_wins,
        "small_pity_win_rate": _safe_rate(small_wins, small_wins + small_losses),
        "current_pity": state["current_pity"],
        "guaranteed_next": state["guaranteed_next"],
        "next_featured_rate": (
            1.0 if state["guaranteed_next"] else rule.featured_rate
        ),
        "hard_pity": rule.hard_pity,
        "remaining_to_hard_pity": max(0, rule.hard_pity - state["current_pity"]),
        "has_history": state["has_history"],
    }


def analyze_account(frame: pd.DataFrame) -> dict[str, Any]:
    five = frame[frame["is_five_star"]]
    pity_values = pd.to_numeric(five["pity_count"], errors="coerce").dropna()
    uids = [uid for uid in frame.get("uid", pd.Series(dtype=str)).unique() if uid]

    pools = {
        pool: analyze_pool(frame, pool)
        for pool in ("character_event", "lightcone_event", "standard", "beginner")
    }
    total_small_wins = sum(item["small_pity_wins"] for item in pools.values())
    total_small_losses = sum(item["off_banner_count"] for item in pools.values())

    return {
        "uid": uids[0] if uids else "—",
        "total_pulls": int(len(frame)),
        "five_stars": int(len(five)),
        "four_stars": int(frame["is_four_star"].sum()) if not frame.empty else 0,
        "average_pity": float(pity_values.mean()) if not pity_values.empty else None,
        "median_pity": float(pity_values.median()) if not pity_values.empty else None,
        "earliest_pity": int(pity_values.min()) if not pity_values.empty else None,
        "latest_pity": int(pity_values.max()) if not pity_values.empty else None,
        "off_banner_count": total_small_losses,
        "small_pity_wins": total_small_wins,
        "small_pity_win_rate": _safe_rate(
            total_small_wins, total_small_wins + total_small_losses
        ),
        "pools": pools,
    }

