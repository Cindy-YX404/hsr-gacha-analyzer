"""Pity counters and independent event-banner guarantee state machines."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


BANNER_DATA_PATH = Path(__file__).resolve().parents[1] / "config" / "banner_data.json"
EVENT_POOLS = {"character_event", "lightcone_event"}


@lru_cache(maxsize=1)
def load_banner_data() -> dict[str, Any]:
    with BANNER_DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalized_names(key: str) -> set[str]:
    return {str(name).strip().casefold() for name in load_banner_data().get(key, [])}


def is_standard_character(name: str) -> bool:
    return str(name).strip().casefold() in _normalized_names("standard_characters")


def is_standard_lightcone(name: str) -> bool:
    return str(name).strip().casefold() in _normalized_names("standard_lightcones")


def is_additional_character_event_off_banner(name: str) -> bool:
    """Return whether a character belongs to the configurable event loss pool."""
    return str(name).strip().casefold() in _normalized_names(
        "character_event_additional_off_banner_characters"
    )


def is_featured_for_banner(name: str, gacha_id: str) -> bool | None:
    """Return metadata result when a banner is configured, otherwise unknown."""
    featured = load_banner_data().get("featured_by_gacha_id", {}).get(str(gacha_id))
    if featured is None:
        return None
    candidates = {str(item).strip().casefold() for item in featured}
    return str(name).strip().casefold() in candidates


def classify_five_star_result(
    name: str,
    pool_type: str,
    guaranteed_next: bool,
    gacha_id: str = "",
) -> tuple[str, bool, bool, bool]:
    """Classify a five-star and return result/off-banner/guaranteed/next-state.

    For event pools, permanent five-stars are authoritative off-banner results.
    Any other five-star is treated as featured when banner-specific metadata is
    unavailable. This conservative fallback is isolated here for easy upgrades.
    """
    if pool_type not in EVENT_POOLS:
        return "not_applicable", False, False, False

    metadata_result = is_featured_for_banner(name, gacha_id)
    if metadata_result is True:
        if guaranteed_next:
            return "guaranteed_up", False, True, False
        return "up", False, False, False

    if pool_type == "character_event":
        off_banner_candidate = is_standard_character(
            name
        ) or is_additional_character_event_off_banner(name)
    else:
        off_banner_candidate = is_standard_lightcone(name)
    if off_banner_candidate or metadata_result is False:
        return "off_banner", True, False, True

    # A non-standard result on an unconfigured banner is treated as featured.
    # The isolated fallback can be replaced as more gacha_id metadata is added.
    if guaranteed_next:
        return "guaranteed_up", False, True, False
    return "up", False, False, False


def apply_pity_and_guarantee(frame: pd.DataFrame) -> pd.DataFrame:
    """Annotate every pull while maintaining independent state per pool."""
    if frame.empty:
        return frame.copy()

    required = {"pool_type", "is_five_star", "name", "gacha_id", "time"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"缺少必要字段：{', '.join(sorted(missing))}")

    result = frame.copy().sort_values(["time", "pull_index"], kind="stable")
    result["pity_count"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["is_off_banner"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result["is_guaranteed"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result["five_star_result_type"] = ""

    for pool_type, indexes in result.groupby("pool_type", sort=False).groups.items():
        pity = 0
        guaranteed_next = False
        for index in indexes:
            pity += 1
            result.at[index, "pity_count"] = pity
            if not bool(result.at[index, "is_five_star"]):
                continue

            classification, off_banner, guaranteed, next_state = classify_five_star_result(
                name=str(result.at[index, "name"]),
                pool_type=str(pool_type),
                guaranteed_next=guaranteed_next,
                gacha_id=str(result.at[index, "gacha_id"]),
            )
            result.at[index, "five_star_result_type"] = classification
            result.at[index, "is_off_banner"] = off_banner
            result.at[index, "is_guaranteed"] = guaranteed
            guaranteed_next = next_state if pool_type in EVENT_POOLS else False
            pity = 0

    return result.sort_values(["time", "pull_index"], kind="stable").reset_index(drop=True)


def current_pool_state(frame: pd.DataFrame, pool_type: str) -> dict[str, Any]:
    """Return current pity and guarantee state derived from visible history."""
    subset = frame[frame["pool_type"].eq(pool_type)].sort_values(
        ["time", "pull_index"], kind="stable"
    )
    if subset.empty:
        return {"current_pity": 0, "guaranteed_next": False, "has_history": False}

    five_stars = subset[subset["is_five_star"]]
    if five_stars.empty:
        current_pity = len(subset)
        guaranteed_next = False
    else:
        last_five_index = five_stars.index[-1]
        ordered_indexes = list(subset.index)
        current_pity = len(ordered_indexes) - ordered_indexes.index(last_five_index) - 1
        guaranteed_next = (
            bool(five_stars.iloc[-1]["is_off_banner"])
            if pool_type in EVENT_POOLS
            else False
        )

    return {
        "current_pity": int(current_pity),
        "guaranteed_next": guaranteed_next,
        "has_history": True,
    }
