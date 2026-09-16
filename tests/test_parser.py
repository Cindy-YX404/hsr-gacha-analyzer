from __future__ import annotations

import json

import pandas as pd
import pytest

from src.api_client import InvalidGachaURLError, parse_gacha_url
from src.parser import extract_records, records_to_dataframe
from src.utils import sanitize_url


def record(record_id: str, time: str, name: str = "物穰") -> dict:
    return {
        "id": record_id,
        "uid": "800000001",
        "gacha_id": "banner",
        "gacha_type": "11",
        "item_id": "lc-1",
        "name": name,
        "item_type": "光锥",
        "rank_type": "3",
        "time": time,
    }


def test_parser_deduplicates_and_sorts_chronologically() -> None:
    rows = [
        record("2", "2025-02-01 10:00:00"),
        record("1", "2025-01-01 10:00:00"),
        record("2", "2025-02-01 10:00:00"),
    ]
    frame = records_to_dataframe(rows)
    assert frame["id"].tolist() == ["1", "2"]
    assert frame["pull_index"].tolist() == [1, 2]
    assert pd.api.types.is_datetime64_any_dtype(frame["time"])


def test_extract_records_accepts_api_and_export_shapes() -> None:
    rows = [record("1", "2025-01-01 10:00:00")]
    assert extract_records({"data": {"list": rows}}) == rows
    assert extract_records({"schema_version": 1, "records": rows}) == rows
    assert extract_records(json.loads(json.dumps(rows))) == rows


def test_parse_official_url_and_mask_authkey() -> None:
    url = (
        "https://public-operation-hkrpg.mihoyo.com/common/hkrpg_gacha_record/"
        "api/getGachaLog?authkey=abcdefghijklmnopqrstuvwxyz&page=1&size=20"
    )
    parsed = parse_gacha_url(url)
    assert parsed.params["authkey"] == "abcdefghijklmnopqrstuvwxyz"
    safe = sanitize_url(url)
    assert "abcdefghijklmnopqrstuvwxyz" not in safe
    assert "authkey=" in safe


def test_rejects_non_official_host() -> None:
    with pytest.raises(InvalidGachaURLError):
        parse_gacha_url("https://example.com/getGachaLog?authkey=secret")

