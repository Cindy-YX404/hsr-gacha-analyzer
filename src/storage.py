"""Private local account history storage keyed by game UID."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.exporter import to_json_bytes
from src.parser import GachaDataError, RAW_COLUMNS, load_json_bytes, records_to_dataframe
from src.pity import apply_pity_and_guarantee


APP_FOLDER_NAME = "HSRGachaAnalyzer"
SAMPLE_ACCOUNT_KEY = "sample"
UID_PATTERN = re.compile(r"\d{5,20}")


def default_storage_directory() -> Path:
    """Return a writable per-user directory that also works in a packaged EXE."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_FOLDER_NAME
    return Path.home() / f".{APP_FOLDER_NAME.lower()}"


class AccountStorage:
    """Persist sanitized pull histories and the last selected account locally."""

    def __init__(self, base_directory: Path | str | None = None) -> None:
        self.base_directory = Path(base_directory) if base_directory else default_storage_directory()
        self.accounts_directory = self.base_directory / "accounts"
        self.settings_path = self.base_directory / "settings.json"

    @staticmethod
    def validate_uid(uid: str) -> str:
        normalized = str(uid).strip()
        if not UID_PATTERN.fullmatch(normalized):
            raise GachaDataError("抽卡记录缺少有效 UID，无法关联到本地账号。")
        return normalized

    def _account_path(self, uid: str) -> Path:
        return self.accounts_directory / f"{self.validate_uid(uid)}.json"

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    def list_account_uids(self) -> list[str]:
        if not self.accounts_directory.exists():
            return []
        uids = [path.stem for path in self.accounts_directory.glob("*.json") if UID_PATTERN.fullmatch(path.stem)]
        return sorted(set(uids), key=lambda value: (len(value), value))

    def has_account(self, uid: str) -> bool:
        try:
            return self._account_path(uid).is_file()
        except GachaDataError:
            return False

    def load_account(self, uid: str) -> pd.DataFrame:
        path = self._account_path(uid)
        if not path.is_file():
            raise GachaDataError(f"未找到 UID {uid} 的本地历史记录。")
        records = load_json_bytes(path.read_bytes())
        frame = records_to_dataframe(records)
        if frame.empty:
            raise GachaDataError(f"UID {uid} 的本地历史记录为空。")
        return apply_pity_and_guarantee(frame)

    def save_account(self, uid: str, frame: pd.DataFrame) -> None:
        normalized_uid = self.validate_uid(uid)
        if frame.empty:
            raise GachaDataError("不能保存空的抽卡记录。")
        frame_uids = {str(value).strip() for value in frame["uid"].dropna() if str(value).strip()}
        if frame_uids != {normalized_uid}:
            raise GachaDataError("本地账号文件只能保存同一个 UID 的记录。")
        self._atomic_write(self._account_path(normalized_uid), to_json_bytes(frame))

    def merge_records(self, records: Iterable[dict[str, Any]]) -> dict[str, pd.DataFrame]:
        """Merge incoming rows into each UID history and return updated frames."""
        incoming = records_to_dataframe(records)
        if incoming.empty:
            raise GachaDataError("没有找到可用的抽卡记录。")
        if incoming["uid"].eq("").any():
            raise GachaDataError("部分抽卡记录缺少 UID，无法保存账号历史。")

        updated: dict[str, pd.DataFrame] = {}
        for raw_uid, group in incoming.groupby("uid", sort=False):
            uid = self.validate_uid(str(raw_uid))
            existing_records: list[dict[str, Any]] = []
            if self.has_account(uid):
                existing_records = load_json_bytes(self._account_path(uid).read_bytes())
            incoming_records = group[RAW_COLUMNS].to_dict(orient="records")
            merged = records_to_dataframe([*existing_records, *incoming_records])
            analyzed = apply_pity_and_guarantee(merged)
            self.save_account(uid, analyzed)
            updated[uid] = analyzed
        return updated

    def get_last_account(self) -> str | None:
        if not self.settings_path.is_file():
            return None
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        value = payload.get("last_account")
        if value == SAMPLE_ACCOUNT_KEY:
            return SAMPLE_ACCOUNT_KEY
        if isinstance(value, str) and UID_PATTERN.fullmatch(value):
            return value
        return None

    def set_last_account(self, uid: str | None) -> None:
        value = SAMPLE_ACCOUNT_KEY if uid is None else self.validate_uid(uid)
        payload = {
            "schema_version": 1,
            "last_account": value,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._atomic_write(self.settings_path, content)
