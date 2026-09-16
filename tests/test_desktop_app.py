from __future__ import annotations

import app
from src.analyzer import analyze_account
from src.parser import load_json_bytes, records_to_dataframe
from src.pity import apply_pity_and_guarantee


def test_desktop_entrypoint_imports_without_starting_ui() -> None:
    assert app.ROOT.exists()
    assert app.SAMPLE_PATH.exists()
    assert app.HSRGachaDesktopApp.__doc__
    assert callable(app.main)


def test_desktop_dependencies_do_not_include_web_framework() -> None:
    requirements = (app.ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "streamlit" not in requirements
    assert "plotly" not in requirements
    assert "matplotlib" in requirements


def test_first_launch_sample_is_realistic_and_anonymous() -> None:
    records = load_json_bytes(app.SAMPLE_PATH.read_bytes())
    assert len(records) == 652
    character_names = {
        row["name"] for row in records if row.get("item_type") == "角色"
    }
    assert character_names <= {
        "四星角色（模拟）",
        "新手五星角色（模拟）",
        "常驻五星角色（模拟）",
        "限定五星角色（模拟）",
    }

    frame = apply_pity_and_guarantee(records_to_dataframe(records))
    summary = analyze_account(frame)
    assert summary["five_stars"] == 8
    assert summary["off_banner_count"] == 2
    assert summary["pools"]["character_event"]["current_pity"] == 38
    assert summary["pools"]["lightcone_event"]["current_pity"] == 24


def test_url_placeholder_is_anonymized_link_shape() -> None:
    assert app.URL_PLACEHOLDER.startswith("https://")
    assert "getGachaLog" in app.URL_PLACEHOLDER
    assert "authkey=..." in app.URL_PLACEHOLDER


def test_pity_color_changes_at_seventy() -> None:
    assert app.HSRGachaDesktopApp._pity_color(69) == app.COLORS["green"]
    assert app.HSRGachaDesktopApp._pity_color(70) == app.COLORS["red"]


def test_real_import_keeps_item_names_and_badges() -> None:
    records = [
        {
            "id": "1",
            "uid": "800000001",
            "gacha_id": "event",
            "gacha_type": "11",
            "item_id": "character-standard",
            "name": "姬子",
            "item_type": "角色",
            "rank_type": "5",
            "time": "2026-01-01 10:00:00",
        },
        {
            "id": "2",
            "uid": "800000001",
            "gacha_id": "event",
            "gacha_type": "11",
            "item_id": "character-featured",
            "name": "阮·梅",
            "item_type": "角色",
            "rank_type": "5",
            "time": "2026-01-02 10:00:00",
        },
    ]
    frame = apply_pity_and_guarantee(records_to_dataframe(records))

    assert [app.HSRGachaDesktopApp._five_star_display_name(row) for _, row in frame.iterrows()] == ["姬子", "阮·梅"]
    assert [app.HSRGachaDesktopApp._result_label(row) for _, row in frame.iterrows()] == ["歪", "保底"]
