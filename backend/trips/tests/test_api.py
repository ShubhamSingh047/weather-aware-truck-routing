from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from trips import services
from trips.domain.geo import build_geometry
from trips.providers.routing import RouteOption
from trips.providers.weather import HourlySeries, OpenMeteoWeather


@pytest.fixture(autouse=True)
def fake_providers(monkeypatch):
    cache.clear()

    def fake_routes(origin, destination, departure_ts, load_lbs):
        return [
            RouteOption(build_geometry([origin, (40.5, -99.0), destination], total_seconds=h * 3600), "I-80", "fake")
            for h in (3.0, 2.5)
        ]

    def fake_fetch(self, cells):
        now = int(timezone.now().timestamp()) // 3600 * 3600 - 3600
        return [HourlySeries(now, [40.0] * 200, [50.0] * 200, [0.0] * 200, [0.0] * 200) for _ in cells]

    monkeypatch.setattr(services, "route_options", fake_routes)
    monkeypatch.setattr(OpenMeteoWeather, "_fetch_chunk", fake_fetch)
    yield
    cache.clear()


def payload(**overrides):
    body = {
        "origin": {"lat": 40.0, "lon": -100.0, "label": "A"},
        "destination": {"lat": 41.0, "lon": -98.0, "label": "B"},
        "departure": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_lbs": 42_000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


def test_plan_returns_ranked_routes_checkpoints_and_heatmap():
    response = APIClient().post("/api/trips/plan", payload(), format="json")
    assert response.status_code == 200
    data = response.json()

    assert [r["id"] for r in data["routes"]] == ["A", "B"]  # sorted by duration
    assert data["recommended_route_id"] == "A"  # equal risk -> faster route
    route = data["routes"][0]
    # 40 mph wind with a 42,000 lb load is Severe by the load rule.
    assert {cp["level"] for cp in route["checkpoints"]} == {"SEVERE"}
    assert route["miles_by_level"]["SEVERE"] == pytest.approx(route["distance_miles"], abs=0.2)

    heatmap = data["heatmap"]
    assert heatmap["frames"] == 4  # hourly frames until the slowest (3 h) route arrives
    assert len(heatmap["risk"]) == 4 * len(heatmap["cells"])


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"interval_miles": 15}, "interval_miles"),
        ({"load_lbs": -1}, "load_lbs"),
        ({"departure": (timezone.now() - timedelta(days=1)).isoformat()}, "departure"),
        ({"departure": (timezone.now() + timedelta(days=10)).isoformat()}, "departure"),
    ],
)
def test_plan_rejects_invalid_input(overrides, field):
    response = APIClient().post("/api/trips/plan", payload(**overrides), format="json")
    assert response.status_code == 400
    assert field in response.json()


def test_health():
    assert APIClient().get("/api/health").json() == {"status": "ok"}


def test_demo_storm_hits_fastest_route_and_changes_recommendation(monkeypatch):
    def far_apart_routes(origin, destination, departure_ts, load_lbs):
        fast = build_geometry([origin, (40.5, -99.0), destination], total_seconds=3 * 3600)
        slow = build_geometry([origin, (38.0, -99.0), destination], total_seconds=4 * 3600)
        return [RouteOption(fast, "I-80", "fake"), RouteOption(slow, "I-70", "fake")]

    def calm_fetch(self, cells):
        now = int(timezone.now().timestamp()) // 3600 * 3600 - 3600
        return [HourlySeries(now, [5.0] * 200, [8.0] * 200, [0.0] * 200, [0.0] * 200) for _ in cells]

    monkeypatch.setattr(services, "route_options", far_apart_routes)
    monkeypatch.setattr(OpenMeteoWeather, "_fetch_chunk", calm_fetch)

    calm = APIClient().post("/api/trips/plan", payload(), format="json").json()
    stormy = APIClient().post("/api/trips/plan", payload(demo_storm=True), format="json").json()

    assert calm["recommended_route_id"] == "A" and calm["demo_storm"] is None
    assert stormy["demo_storm"] is not None
    assert stormy["routes"][0]["miles_by_level"]["NO_TRAVEL"] > 0
    assert stormy["recommended_route_id"] == "B"
    assert max(v for v in stormy["heatmap"]["risk"] if v is not None) == 4


def test_demo_storm_can_target_the_selected_route(monkeypatch):
    def far_apart_routes(origin, destination, departure_ts, load_lbs):
        fast = build_geometry([origin, (40.5, -99.0), destination], total_seconds=3 * 3600)
        slow = build_geometry([origin, (38.0, -99.0), destination], total_seconds=4 * 3600)
        return [RouteOption(fast, "I-80", "fake"), RouteOption(slow, "I-70", "fake")]

    def calm_fetch(self, cells):
        now = int(timezone.now().timestamp()) // 3600 * 3600 - 3600
        return [HourlySeries(now, [5.0] * 200, [8.0] * 200, [0.0] * 200, [0.0] * 200) for _ in cells]

    monkeypatch.setattr(services, "route_options", far_apart_routes)
    monkeypatch.setattr(OpenMeteoWeather, "_fetch_chunk", calm_fetch)

    data = APIClient().post("/api/trips/plan", payload(demo_storm=True, storm_route="B"), format="json").json()

    assert data["demo_storm"]["route_id"] == "B"
    assert data["routes"][1]["miles_by_level"]["NO_TRAVEL"] > 0
    assert data["routes"][0]["miles_by_level"]["NO_TRAVEL"] == 0
    assert data["recommended_route_id"] == "A"


def test_storm_route_must_be_a_route_id():
    response = APIClient().post("/api/trips/plan", payload(demo_storm=True, storm_route="Z"), format="json")
    assert response.status_code == 400 and "storm_route" in response.json()
