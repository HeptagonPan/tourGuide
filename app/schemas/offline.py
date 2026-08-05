from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OfflinePoi(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    district: str = Field(min_length=1)
    area: str = Field(min_length=1)
    longitude: float = Field(ge=120.8, le=122.2)
    latitude: float = Field(ge=30.6, le=31.9)
    suggested_duration_minutes: int = Field(ge=30, le=480)
    admission_cents: int = Field(ge=0)
    opening_note: str = Field(min_length=1)
    is_general_highlight: bool = False
    interests: list[str] = Field(min_length=1)
    source_id: str = Field(min_length=1)
    verified_at: date


class OfflineRouteEdge(BaseModel):
    origin_poi_id: str = Field(min_length=1)
    destination_poi_id: str = Field(min_length=1)
    transport_mode: Literal["walk", "metro", "bus", "mixed"]
    duration_minutes: int = Field(ge=1)
    distance_meters: int = Field(ge=1)
    cost_cents: int = Field(ge=0)
    summary: str = Field(min_length=1)
    is_bidirectional: bool = True
    source_id: str = Field(min_length=1)
    verified_at: date


class OfflineRoutePath(BaseModel):
    origin_poi_id: str
    destination_poi_id: str
    edges: list[OfflineRouteEdge] = Field(min_length=1)
    duration_minutes: int = Field(ge=1)
    distance_meters: int = Field(ge=1)
    cost_cents: int = Field(ge=0)
    instructions: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class OfflineMetadata(BaseModel):
    schema_version: int = Field(ge=1)
    data_version: str = Field(min_length=1)
    generated_at: datetime
    poi_count: int = Field(ge=1)
    route_edge_count: int = Field(ge=1)
