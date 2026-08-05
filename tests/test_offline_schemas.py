from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.offline import OfflinePoi, OfflineRouteEdge


def test_offline_poi_rejects_missing_interest() -> None:
    with pytest.raises(ValidationError):
        OfflinePoi(
            id="the-bund",
            name="外滩",
            district="黄浦区",
            area="外滩与南京东路",
            longitude=121.4901,
            latitude=31.2415,
            suggested_duration_minutes=90,
            admission_cents=0,
            opening_note="开放区域以现场公告为准",
            is_general_highlight=True,
            interests=[],
            source_id="osm-and-official-the-bund",
            verified_at=date(2026, 8, 5),
        )


def test_route_edge_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        OfflineRouteEdge(
            origin_poi_id="the-bund",
            destination_poi_id="nanjing-road",
            transport_mode="walk",
            duration_minutes=-1,
            distance_meters=900,
            cost_cents=0,
            summary="沿南京东路步行",
            is_bidirectional=True,
            source_id="manual-route-estimate",
            verified_at=date(2026, 8, 5),
        )
