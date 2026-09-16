from __future__ import annotations

from src.api_client import GachaAPIClient


class FakeResponse:
    def __init__(self, records: list[dict]):
        self.status_code = 200
        self.headers = {}
        self._records = records

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"retcode": 0, "message": "OK", "data": {"list": self._records}}


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls: list[dict] = []

    def get(self, endpoint: str, params: dict, timeout: int) -> FakeResponse:
        self.calls.append(params.copy())
        if params["page"] == "1":
            return FakeResponse(
                [
                    {"id": "2", "gacha_type": params["gacha_type"]},
                    {"id": "1", "gacha_type": params["gacha_type"]},
                ]
            )
        return FakeResponse([])


def test_client_paginates_with_end_id() -> None:
    session = FakeSession()
    client = GachaAPIClient(session=session, delay=0, sleep_fn=lambda _: None)
    url = (
        "https://public-operation-hkrpg.mihoyo.com/common/hkrpg_gacha_record/"
        "api/getGachaLog?authkey=test-secret"
    )
    records = client.fetch_all(url, gacha_types=("11",), page_size=2)
    assert len(records) == 2
    assert session.calls[0]["end_id"] == "0"
    assert session.calls[1]["end_id"] == "1"

