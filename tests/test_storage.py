from __future__ import annotations

from pathlib import Path

from src.storage import AccountStorage, SAMPLE_ACCOUNT_KEY


def make_record(record_id: str, uid: str, time: str, name: str = "物穰") -> dict:
    return {
        "id": record_id,
        "uid": uid,
        "gacha_id": "banner",
        "gacha_type": "11",
        "item_id": f"item-{record_id}",
        "name": name,
        "item_type": "光锥",
        "rank_type": "3",
        "time": time,
        "authkey": "must-never-be-persisted",
    }


def test_storage_merges_and_deduplicates_by_uid(tmp_path: Path) -> None:
    storage = AccountStorage(tmp_path)
    uid = "800000001"
    first = storage.merge_records(
        [
            make_record("1", uid, "2026-01-01 10:00:00"),
            make_record("2", uid, "2026-01-02 10:00:00"),
        ]
    )[uid]
    assert len(first) == 2

    merged = storage.merge_records(
        [
            make_record("2", uid, "2026-01-02 10:00:00"),
            make_record("3", uid, "2026-01-03 10:00:00"),
        ]
    )[uid]
    assert merged["id"].tolist() == ["1", "2", "3"]
    assert "must-never-be-persisted" not in (tmp_path / "accounts" / f"{uid}.json").read_text(encoding="utf-8")


def test_storage_separates_accounts_and_remembers_selection(tmp_path: Path) -> None:
    storage = AccountStorage(tmp_path)
    first_uid = "800000001"
    second_uid = "900000002"
    storage.merge_records([make_record("1", first_uid, "2026-01-01 10:00:00")])
    storage.merge_records([make_record("2", second_uid, "2026-01-02 10:00:00")])

    assert storage.list_account_uids() == [first_uid, second_uid]
    assert len(storage.load_account(first_uid)) == 1
    assert len(storage.load_account(second_uid)) == 1

    storage.set_last_account(second_uid)
    assert storage.get_last_account() == second_uid
    storage.set_last_account(None)
    assert storage.get_last_account() == SAMPLE_ACCOUNT_KEY
