from app.repositories.presets import PresetRepository


def test_city_presets_have_exact_supported_names(repository: PresetRepository) -> None:
    names = {city.name for city in repository.load_cities()}

    assert names == {
        "合肥",
        "芜湖",
        "蚌埠",
        "淮南",
        "阜阳",
        "安庆",
        "黄山",
        "马鞍山",
        "滁州",
        "南京",
    }


def test_every_city_has_a_railway_station_and_nearby_airport(
    repository: PresetRepository,
) -> None:
    for city in repository.load_cities():
        assert city.railway_stations
        assert city.nearby_airports


def test_interest_presets_cover_all_questionnaire_choices(
    repository: PresetRepository,
) -> None:
    interest_ids = {interest.id for interest in repository.load_interests()}

    assert interest_ids == {
        "food",
        "nature",
        "culture",
        "family",
        "shopping",
        "night_view",
    }
