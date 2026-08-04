from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from app.repositories.presets import PresetRepository
from app.schemas.trip import TripRequest


@pytest.fixture
def valid_request_data() -> dict[str, Any]:
    """提供一份可复用的有效问卷数据。"""
    return {
        "origin_city": "合肥",
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "relationship": "couple",
        "start_date": "2026-10-02",
        "end_date": "2026-10-05",
        "budget_cents": 600_000,
        "budget_includes_intercity": True,
        "interests": ["food", "culture"],
        "intercity_preference": "balanced",
        "local_transport_preference": "metro",
    }


@pytest.fixture
def request_factory(
    valid_request_data: dict[str, Any],
) -> Callable[..., TripRequest]:
    """按需覆盖字段并构造问卷模型。"""

    def factory(**overrides: Any) -> TripRequest:
        data = deepcopy(valid_request_data)
        data.update(overrides)
        return TripRequest.model_validate(data)

    return factory


@pytest.fixture
def repository() -> PresetRepository:
    """返回使用项目真实预设文件的数据仓库。"""
    return PresetRepository()
