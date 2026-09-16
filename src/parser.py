"""Normalize API, JSON and CSV records into one canonical DataFrame."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Iterable

import pandas as pd

from config.gacha_rules import GACHA_TYPE_TO_POOL


RAW_COLUMNS = [
    "id",
    "uid",
    "gacha_id",
    "gacha_type",
    "item_id",
    "name",
    "item_type",
    "rank_type",
    "time",
]

DERIVED_COLUMNS = [
    "pool_type",
    "is_five_star",
    "is_four_star",
    "pull_index",
    "pity_count",
    "is_off_banner",
    "is_guaranteed",
    "five_star_result_type",
]


class GachaDataError(ValueError):
    pass


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Accept an API response, exported wrapper, or a plain record list."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        raise GachaDataError("JSON 顶层必须是对象或记录数组。")

    for key in ("records", "pull_history", "list"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return [row for row in data["list"] if isinstance(row, dict)]

    raise GachaDataError("JSON 中未找到抽卡记录数组。")


def load_json_bytes(content: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GachaDataError("JSON 文件无法解析。") from exc
    return extract_records(payload)


def load_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    try:
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise GachaDataError("CSV 文件无法解析。") from exc
    return frame.to_dict(orient="records")


def records_to_dataframe(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Clean, deduplicate and chronologically sort gacha records."""
    frame = pd.DataFrame(list(records))
    if frame.empty:
        return empty_gacha_dataframe()

    for column in RAW_COLUMNS:
        if column not in frame.columns:
            frame[column] = None

    frame = frame[RAW_COLUMNS].copy()
    for column in RAW_COLUMNS[:-1]:
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    frame["gacha_type"] = frame["gacha_type"].str.replace(r"\.0$", "", regex=True)
    frame["rank_type"] = pd.to_numeric(frame["rank_type"], errors="coerce").astype("Int64")
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame = frame.dropna(subset=["time"])
    frame = frame[frame["name"].ne("")]

    fallback_key = (
        frame["time"].astype(str)
        + "|"
        + frame["gacha_type"]
        + "|"
        + frame["name"]
        + "|"
        + frame["item_id"]
    )
    frame["_dedupe_key"] = frame["id"].where(frame["id"].ne(""), fallback_key)
    frame = frame.drop_duplicates(subset=["_dedupe_key"], keep="first")

    frame["_id_numeric"] = pd.to_numeric(frame["id"], errors="coerce")
    frame = frame.sort_values(
        ["time", "_id_numeric", "id"],
        ascending=[True, True, True],
        kind="stable",
        na_position="last",
    ).drop(columns=["_dedupe_key", "_id_numeric"])

    frame["pool_type"] = frame["gacha_type"].map(GACHA_TYPE_TO_POOL).fillna("unknown")
    frame["is_five_star"] = frame["rank_type"].eq(5)
    frame["is_four_star"] = frame["rank_type"].eq(4)
    frame["pull_index"] = frame.groupby("pool_type", sort=False).cumcount() + 1
    frame["pity_count"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["is_off_banner"] = pd.Series(pd.NA, index=frame.index, dtype="boolean")
    frame["is_guaranteed"] = pd.Series(pd.NA, index=frame.index, dtype="boolean")
    frame["five_star_result_type"] = ""
    return frame.reset_index(drop=True)


def empty_gacha_dataframe() -> pd.DataFrame:
    frame = pd.DataFrame(columns=RAW_COLUMNS + DERIVED_COLUMNS)
    frame["time"] = pd.to_datetime(frame["time"])
    frame["rank_type"] = frame["rank_type"].astype("Int64")
    frame["pity_count"] = frame["pity_count"].astype("Int64")
    frame["is_five_star"] = frame["is_five_star"].astype(bool)
    frame["is_four_star"] = frame["is_four_star"].astype(bool)
    frame["is_off_banner"] = frame["is_off_banner"].astype("boolean")
    frame["is_guaranteed"] = frame["is_guaranteed"].astype("boolean")
    return frame

