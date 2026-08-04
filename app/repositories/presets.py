import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.config import Settings
from app.schemas.trip import CityPreset, InterestPreset, ReferenceCategory, ReferencePrice

PresetModel = TypeVar("PresetModel", bound=BaseModel)


class PresetDataError(ValueError):
    """表示本地预设文件缺失或内容无效。"""


class PresetRepository:
    """读取并校验项目内的 JSON 预设数据。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Settings().data_dir

    def load_cities(self) -> list[CityPreset]:
        """读取支持的出发城市。"""
        return self._load_models("presets/cities.json", CityPreset)

    def load_interests(self) -> list[InterestPreset]:
        """读取问卷兴趣选项。"""
        return self._load_models("presets/interests.json", InterestPreset)

    def load_reference_prices(self) -> list[ReferencePrice]:
        """读取价格记录，并拒绝会破坏来源追踪的重复 ID。"""
        records = self._load_models("reference/prices.json", ReferencePrice)
        record_ids = [record.id for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise PresetDataError("参考价格存在重复 ID")
        return records

    def find_prices(
        self,
        category: ReferenceCategory | str,
        origin_city: str | None = None,
    ) -> list[ReferencePrice]:
        """按类别和可选出发城市筛选参考价格。"""
        normalized_category = ReferenceCategory(category)
        return [
            record
            for record in self.load_reference_prices()
            if record.category is normalized_category
            and (origin_city is None or record.origin_city == origin_city)
        ]

    def _load_models(
        self,
        relative_path: str,
        model_type: type[PresetModel],
    ) -> list[PresetModel]:
        path = self._data_dir / relative_path
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
            return TypeAdapter(list[model_type]).validate_python(raw_data)
        except FileNotFoundError as error:
            raise PresetDataError(f"预设数据文件不存在: {relative_path}") from error
        except (json.JSONDecodeError, ValidationError) as error:
            raise PresetDataError(f"预设数据文件无效: {relative_path}") from error
