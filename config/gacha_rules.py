"""Central gacha rules and pool mappings.

Keep game-rule constants here so the parser, analytics engine and UI use the
same assumptions.  Values can be updated without touching business logic.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_PAGE_SIZE = 20
REQUEST_DELAY_SECONDS = 0.35
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 15


GACHA_TYPE_TO_POOL = {
    "1": "standard",
    "2": "beginner",
    "11": "character_event",
    "12": "lightcone_event",
}

POOL_LABELS = {
    "all": "全部跃迁",
    "character_event": "角色活动跃迁",
    "lightcone_event": "光锥活动跃迁",
    "standard": "常驻跃迁",
    "beginner": "新手跃迁",
    "unknown": "其他跃迁",
}


@dataclass(frozen=True)
class PoolRule:
    tracks_guarantee: bool


POOL_RULES = {
    "character_event": PoolRule(
        tracks_guarantee=True,
    ),
    "lightcone_event": PoolRule(
        tracks_guarantee=True,
    ),
    "standard": PoolRule(
        tracks_guarantee=False,
    ),
    "beginner": PoolRule(
        tracks_guarantee=False,
    ),
    "unknown": PoolRule(
        tracks_guarantee=False,
    ),
}


SUPPORTED_GACHA_TYPES = tuple(GACHA_TYPE_TO_POOL)
