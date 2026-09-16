from __future__ import annotations

from src.analyzer import analyze_account
from src.parser import records_to_dataframe
from src.pity import apply_pity_and_guarantee, classify_five_star_result, current_pool_state


def make_record(index: int, name: str, gacha_type: str, item_type: str = "角色") -> dict:
    return {
        "id": str(index),
        "uid": "800000001",
        "gacha_id": "test_banner",
        "gacha_type": gacha_type,
        "item_id": f"item-{index}",
        "name": name,
        "item_type": item_type,
        "rank_type": "5",
        "time": f"2025-01-{index:02d} 12:00:00",
    }


def test_character_event_state_machine_up_loss_guaranteed_up() -> None:
    records = [
        make_record(1, "阮·梅", "11"),
        make_record(2, "姬子", "11"),
        make_record(3, "飞霄", "11"),
        make_record(4, "黄泉", "11"),
    ]

    analyzed = apply_pity_and_guarantee(records_to_dataframe(records))
    five = analyzed[analyzed["is_five_star"]]

    assert five["five_star_result_type"].tolist() == [
        "up",
        "off_banner",
        "guaranteed_up",
        "up",
    ]
    assert five["is_off_banner"].tolist() == [False, True, False, False]
    assert five["is_guaranteed"].tolist() == [False, False, True, False]
    assert current_pool_state(analyzed, "character_event")["guaranteed_next"] is False


def test_standard_himeko_is_never_off_banner() -> None:
    analyzed = apply_pity_and_guarantee(
        records_to_dataframe([make_record(1, "姬子", "1")])
    )
    row = analyzed.iloc[0]
    assert bool(row["is_off_banner"]) is False
    assert bool(row["is_guaranteed"]) is False
    assert row["five_star_result_type"] == "not_applicable"


def test_lightcone_loss_then_guaranteed() -> None:
    records = [
        make_record(1, "如泥酣眠", "12", "光锥"),
        make_record(2, "镜中故我", "12", "光锥"),
    ]
    analyzed = apply_pity_and_guarantee(records_to_dataframe(records))
    assert analyzed["five_star_result_type"].tolist() == ["off_banner", "guaranteed_up"]
    assert analyzed["is_guaranteed"].tolist() == [False, True]
    assert current_pool_state(analyzed, "lightcone_event")["guaranteed_next"] is False


def test_character_and_lightcone_guarantees_are_independent() -> None:
    records = [
        make_record(1, "姬子", "11"),
        make_record(2, "镜中故我", "12", "光锥"),
        make_record(3, "飞霄", "11"),
    ]
    analyzed = apply_pity_and_guarantee(records_to_dataframe(records))
    character = analyzed[analyzed["pool_type"].eq("character_event")]
    lightcone = analyzed[analyzed["pool_type"].eq("lightcone_event")]
    assert character["five_star_result_type"].tolist() == ["off_banner", "guaranteed_up"]
    assert lightcone["five_star_result_type"].tolist() == ["up"]


def test_small_pity_win_rate_excludes_guaranteed_up() -> None:
    records = [
        make_record(1, "阮·梅", "11"),
        make_record(2, "姬子", "11"),
        make_record(3, "飞霄", "11"),
        make_record(4, "黄泉", "11"),
    ]
    analyzed = apply_pity_and_guarantee(records_to_dataframe(records))
    stats = analyze_account(analyzed)["pools"]["character_event"]
    assert stats["small_pity_wins"] == 2
    assert stats["off_banner_count"] == 1
    assert stats["guaranteed_wins"] == 1
    assert stats["small_pity_win_rate"] == 2 / 3


def test_pity_counts_reset_after_five_star() -> None:
    records = [
        {**make_record(1, "琥珀", "11", "光锥"), "rank_type": "3"},
        {**make_record(2, "三月七", "11"), "rank_type": "4"},
        make_record(3, "阮·梅", "11"),
        {**make_record(4, "物穰", "11", "光锥"), "rank_type": "3"},
        make_record(5, "黄泉", "11"),
    ]
    analyzed = apply_pity_and_guarantee(records_to_dataframe(records))
    assert analyzed["pity_count"].tolist() == [1, 2, 3, 1, 2]
    assert current_pool_state(analyzed, "character_event")["current_pity"] == 0


def test_celestial_invitation_characters_are_character_event_losses() -> None:
    for name in ["银狼", "希儿", "符玄", "云璃", "刃", "银枝"]:
        result, off_banner, guaranteed, next_state = classify_five_star_result(
            name=name,
            pool_type="character_event",
            guaranteed_next=False,
        )
        assert result == "off_banner", name
        assert off_banner is True, name
        assert guaranteed is False, name
        assert next_state is True, name
