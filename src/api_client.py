"""Safe, rate-limited client for the Honkai: Star Rail gacha log API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

import requests

from config.gacha_rules import (
    DEFAULT_PAGE_SIZE,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    SUPPORTED_GACHA_TYPES,
)
from src.utils import redact_authkey, sanitize_url


ALLOWED_API_HOSTS = {
    "public-operation-hkrpg.mihoyo.com",
    "public-operation-hkrpg.hoyoverse.com",
}


class GachaAPIError(RuntimeError):
    """Base class for safe, user-facing API failures."""


class InvalidGachaURLError(GachaAPIError):
    pass


class AuthKeyExpiredError(GachaAPIError):
    pass


class RateLimitError(GachaAPIError):
    pass


@dataclass(frozen=True)
class ParsedGachaURL:
    endpoint: str
    params: dict[str, str]

    @property
    def safe_url(self) -> str:
        from urllib.parse import urlencode

        return sanitize_url(f"{self.endpoint}?{urlencode(self.params)}")


def parse_gacha_url(url: str) -> ParsedGachaURL:
    """Validate the official API URL and extract request parameters."""
    raw = (url or "").strip()
    if not raw:
        raise InvalidGachaURLError("请粘贴抽卡记录链接。")

    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise InvalidGachaURLError("链接格式无效。") from exc

    if parts.scheme != "https" or parts.hostname not in ALLOWED_API_HOSTS:
        raise InvalidGachaURLError("仅支持官方 HTTPS 抽卡记录 API 域名。")
    if not parts.path.endswith("/getGachaLog"):
        raise InvalidGachaURLError("链接不是 getGachaLog 抽卡记录接口。")

    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    if not params.get("authkey") or params["authkey"] == "<YOUR_AUTHKEY>":
        raise InvalidGachaURLError("链接中缺少有效的 authkey。")

    endpoint = f"{parts.scheme}://{parts.netloc}{parts.path}"
    return ParsedGachaURL(endpoint=endpoint, params=params)


class GachaAPIClient:
    """Fetch complete gacha history across supported pool types."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        delay: float = REQUEST_DELAY_SECONDS,
        max_retries: int = MAX_RETRIES,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.max_retries = max(1, max_retries)
        self.sleep_fn = sleep_fn
        self.session.headers.update(
            {
                "User-Agent": "HSR-Gacha-Analyzer/1.0 (personal local data manager)",
                "Accept": "application/json",
            }
        )

    def fetch_all(
        self,
        url: str,
        gacha_types: tuple[str, ...] = SUPPORTED_GACHA_TYPES,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        parsed = parse_gacha_url(url)
        records: list[dict[str, Any]] = []
        for position, gacha_type in enumerate(gacha_types):
            records.extend(self._fetch_pool(parsed, str(gacha_type), page_size))
            if position < len(gacha_types) - 1:
                self.sleep_fn(self.delay)
        return self._deduplicate(records)

    def _fetch_pool(
        self, parsed: ParsedGachaURL, gacha_type: str, page_size: int
    ) -> list[dict[str, Any]]:
        page = 1
        end_id = "0"
        pool_records: list[dict[str, Any]] = []

        while True:
            params = parsed.params.copy()
            params.update(
                {
                    "gacha_type": gacha_type,
                    "page": str(page),
                    "size": str(page_size),
                    "end_id": end_id,
                }
            )
            payload = self._request_json(parsed.endpoint, params)
            page_records = self._extract_records(payload)
            if not page_records:
                break

            pool_records.extend(page_records)
            new_end_id = str(page_records[-1].get("id", ""))
            if len(page_records) < page_size or not new_end_id or new_end_id == end_id:
                break

            end_id = new_end_id
            page += 1
            self.sleep_fn(self.delay)

        return pool_records

    def _request_json(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(endpoint, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    if attempt == self.max_retries - 1:
                        raise RateLimitError("请求过于频繁，请稍后重试。")
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else 1.5 * (attempt + 1)
                    self.sleep_fn(min(wait, 10.0))
                    continue
                response.raise_for_status()
                payload = response.json()
                self._raise_for_api_error(payload)
                return payload
            except (RateLimitError, AuthKeyExpiredError):
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    self.sleep_fn(1.5 * (attempt + 1))

        safe_message = redact_authkey(str(last_error or "unknown network error"))
        raise GachaAPIError(f"网络请求失败：{safe_message}") from last_error

    @staticmethod
    def _raise_for_api_error(payload: dict[str, Any]) -> None:
        retcode = payload.get("retcode", 0)
        if retcode in (0, None):
            return
        message = redact_authkey(str(payload.get("message", "API 返回错误")))
        lowered = message.lower()
        if retcode in {-100, -101, -1001, -110} or "authkey" in lowered:
            raise AuthKeyExpiredError("authkey 无效或已过期，请重新获取抽卡记录链接。")
        raise GachaAPIError(f"API 返回错误（{retcode}）：{message}")

    @staticmethod
    def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return []
        records = data.get("list") or []
        return [item for item in records if isinstance(item, dict)]

    @staticmethod
    def _deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        output: list[dict[str, Any]] = []
        for record in records:
            key = str(record.get("id") or "|").strip()
            if not key or key == "|":
                key = "|".join(
                    str(record.get(field, ""))
                    for field in ("time", "gacha_type", "name", "item_id")
                )
            if key not in seen:
                seen.add(key)
                output.append(record)
        return output
