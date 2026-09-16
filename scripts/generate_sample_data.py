"""Generate deterministic, anonymous sample history for the first app launch."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "sample_gacha.json"


def build_pool(
    *,
    gacha_type: str,
    total_pulls: int,
    five_stars: dict[int, tuple[str, str]],
    start: datetime,
    id_start: int,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    event_kind = "character" if gacha_type == "11" else "lightcone"
    for position in range(1, total_pulls + 1):
        record_time = start + timedelta(days=position // 2, hours=(position % 2) * 3)
        if position in five_stars:
            name, item_type = five_stars[position]
            rank = "5"
        elif position % 10 == 0 or position % 27 == 0:
            name = "四星角色（模拟）" if position % 20 == 0 else "四星光锥（模拟）"
            item_type = "角色" if "角色" in name else "光锥"
            rank = "4"
        else:
            name = "三星光锥（模拟）"
            item_type = "光锥"
            rank = "3"

        banner_number = 1 + position // 90
        records.append(
            {
                "id": str(id_start + position),
                "uid": "800000000",
                "gacha_id": f"sample_{event_kind}_{banner_number}",
                "gacha_type": gacha_type,
                "item_id": f"sample-{gacha_type}-{rank}-{position % 17}",
                "name": name,
                "item_type": item_type,
                "rank_type": rank,
                "time": record_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return records


def main() -> None:
    records: list[dict[str, str]] = []
    records += build_pool(
        gacha_type="2",
        total_pulls=50,
        five_stars={43: ("新手五星角色（模拟）", "角色")},
        start=datetime(2026, 1, 1, 10, 0),
        id_start=1_000_000,
    )
    records += build_pool(
        gacha_type="1",
        total_pulls=180,
        five_stars={
            79: ("常驻五星光锥（模拟）", "光锥"),
            163: ("常驻五星角色（模拟）", "角色"),
        },
        start=datetime(2026, 1, 5, 12, 0),
        id_start=2_000_000,
    )
    records += build_pool(
        gacha_type="11",
        total_pulls=269,
        five_stars={
            74: ("限定五星角色（模拟）", "角色"),
            155: ("常驻五星角色（模拟）", "角色"),
            231: ("限定五星角色（模拟）", "角色"),
        },
        start=datetime(2026, 3, 1, 18, 0),
        id_start=3_000_000,
    )
    records += build_pool(
        gacha_type="12",
        total_pulls=153,
        five_stars={
            68: ("常驻五星光锥（模拟）", "光锥"),
            129: ("限定五星光锥（模拟）", "光锥"),
        },
        start=datetime(2026, 4, 15, 20, 0),
        id_start=4_000_000,
    )
    payload = {
        "schema_version": 1,
        "sample_note": "Deterministic anonymous demo data. Contains no real character or light-cone names.",
        "records": records,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(records)} records -> {OUTPUT}")


if __name__ == "__main__":
    main()

