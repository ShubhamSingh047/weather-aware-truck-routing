import pytest
from django.core.cache import cache

from trips.domain.geo import backtrack_ratio, build_geometry, loop_detour
from trips.domain.heatmap import corridor_cells, grid_step
from trips.providers import routing
from trips.providers.routing import RouteOption, route_options
from trips.providers.weather import HourlySeries, OpenMeteoWeather, snap

START = 1_800_000_000 - (1_800_000_000 % 3600)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestHourlySeries:
    series = HourlySeries(
        start_ts=START,
        wind_mph=[10, 20, 30],
        gust_mph=[15, 25, 35],
        rain_in=[0.0, 0.2, 0.4],
        snow_in=[0.0, 0.0, 1.0],
    )

    def test_wind_uses_nearest_hour(self):
        assert self.series.conditions_at(START + 20 * 60).wind_mph == 10
        assert self.series.conditions_at(START + 40 * 60).wind_mph == 20

    def test_precipitation_uses_the_hour_that_contains_the_eta(self):
        # Rain stamped 01:00 is the total for 00:00–01:00.
        assert self.series.conditions_at(START + 20 * 60).rain_in_hr == 0.2
        assert self.series.conditions_at(START + 3600).rain_in_hr == 0.2
        assert self.series.conditions_at(START + 3601).rain_in_hr == 0.4

    def test_outside_forecast_window_is_missing(self):
        assert self.series.conditions_at(START + 5 * 3600) is None


def test_open_meteo_parse_adds_showers_to_rain():
    series = OpenMeteoWeather._parse({"hourly": {
        "time": [START, START + 3600],
        "wind_speed_10m": [5, 6],
        "wind_gusts_10m": [9, 10],
        "rain": [0.1, None],
        "showers": [0.05, 0.2],
        "snowfall": [0, 0],
    }})
    assert series.rain_in == [pytest.approx(0.15), None]


def test_prefetch_uses_cache_for_known_cells(monkeypatch):
    calls = []

    def fake_fetch(self, cells):
        calls.append(list(cells))
        return [HourlySeries(START, [1.0], [1.0], [0.0], [0.0]) for _ in cells]

    monkeypatch.setattr(OpenMeteoWeather, "_fetch_chunk", fake_fetch)
    cells = [snap(41.88, -87.63, 0.1), snap(41.5, -88.2, 0.1), snap(39.7, -105.0, 0.1)]
    first = OpenMeteoWeather()
    first.prefetch(cells + cells)  # duplicates are fetched once
    second = OpenMeteoWeather()
    second.prefetch(cells)
    assert first.locations_fetched == 3
    assert second.locations_fetched == 0 and second.locations_from_cache == 3
    assert len(calls) == 1


def test_corridor_cells_follow_route():
    geometry = build_geometry([(40.0, -100.0), (40.0, -95.0)], total_seconds=5 * 3600)
    step = grid_step([geometry])
    cells = corridor_cells([geometry], step)
    assert cells
    assert all(39.0 <= lat <= 41.0 for lat, _ in cells)
    assert all(-101 <= lon <= -94 for _, lon in cells)


class FakeProvider:
    """Direct alternatives, plus one fixed route for via points north or south of lat 40."""

    name = "fake"

    def __init__(self, direct, north=None, south=None):
        self.direct, self.north, self.south = direct, north, south
        self.via_calls = 0

    def fetch(self, points, departure_ts, load_lbs, alternatives):
        if len(points) == 2:
            return self.direct
        self.via_calls += 1
        route = self.north if points[1][0] > 40 else self.south
        return [route] if route else []


@pytest.fixture
def no_cities(monkeypatch):
    monkeypatch.setattr(routing, "US_VIA_CITIES", ())


def densify(coords, step_deg=0.01):
    """Real routes have a vertex every few hundred metres; mimic that."""
    out = [coords[0]]
    for (lat0, lon0), (lat1, lon1) in zip(coords, coords[1:]):
        n = max(1, round(max(abs(lat1 - lat0), abs(lon1 - lon0)) / step_deg))
        out += [(lat0 + (lat1 - lat0) * k / n, lon0 + (lon1 - lon0) * k / n) for k in range(1, n + 1)]
    return out


def dense_geometry(coords, hours=2.0):
    return build_geometry(densify(coords), total_seconds=hours * 3600)


def option(coords, hours=2.0):
    return RouteOption(dense_geometry(coords, hours), "", "fake")


def test_route_options_adds_distinct_via_routes_until_three(no_cities):
    straight = option([(40.0, -100.0), (40.0, -98.0)])
    duplicate = option([(40.0, -100.0), (40.0, -98.0)], hours=2.1)
    north = option([(40.0, -100.0), (40.4, -99.0), (40.0, -98.0)])
    south = option([(40.0, -100.0), (39.6, -99.0), (40.0, -98.0)])
    provider = FakeProvider(direct=[straight, duplicate], north=north, south=south)

    routes = route_options((40.0, -100.0), (40.0, -98.0), START, 30_000, provider=provider)

    assert [r.geometry for r in routes] == [straight.geometry, south.geometry, north.geometry]


def test_route_options_rejects_long_detours(no_cities):
    straight = option([(40.0, -100.0), (40.0, -98.0)])
    detour = option([(40.0, -100.0), (43.0, -99.0), (40.0, -98.0)])
    provider = FakeProvider(direct=[straight], north=detour, south=detour)
    assert route_options((40.0, -100.0), (40.0, -98.0), START, 30_000, provider=provider) == [straight]


def test_backtrack_ratio_flags_out_and_back_spur():
    straight = dense_geometry([(40.0, -100.0), (40.0, -98.0)])
    spur = dense_geometry([(40.0, -100.0), (40.0, -99.0), (40.5, -99.0), (40.0, -99.0), (40.0, -98.0)], hours=2.5)
    assert backtrack_ratio(straight) == 0
    assert backtrack_ratio(spur) > 0.1


def test_route_options_rejects_via_routes_with_spurs(no_cities):
    straight = option([(40.0, -100.0), (40.0, -98.0)])
    spur = option([(40.0, -100.0), (40.0, -99.0), (40.5, -99.0), (40.0, -99.0), (40.0, -98.0)])
    provider = FakeProvider(direct=[straight], north=spur, south=spur)
    assert route_options((40.0, -100.0), (40.0, -98.0), START, 30_000, provider=provider) == [straight]


def test_via_cities_skip_towns_on_chosen_routes():
    chicago, denver = (41.88, -87.63), (39.74, -104.99)
    i80 = dense_geometry([chicago, (41.26, -95.93), denver], hours=17)  # through Omaha
    picked = routing._via_cities(chicago, denver, [i80], tried=set(), limit=3)
    names = [name for name, _, _ in picked]
    assert names and "Omaha, NE" not in names and "Lincoln, NE" not in names
    assert all(routing.haversine_miles(chicago, (lat, lon)) > 0.15 * routing.haversine_miles(chicago, denver)
               for _, lat, lon in picked)


def test_loop_detour_flags_loop_on_parallel_roads():
    base = dense_geometry([(40.0, -100.0), (40.0, -98.0)])
    # Leaves at -99.2, drives ~35 mi north and back on a road ~7 mi east, rejoins at -99.07.
    loop = dense_geometry([(40.0, -100.0), (40.0, -99.2), (40.5, -99.2), (40.5, -99.07), (40.0, -99.07),
                           (40.0, -98.0)], hours=2.5)
    south = dense_geometry([(40.0, -100.0), (39.6, -99.0), (40.0, -98.0)], hours=2.2)
    assert loop_detour(loop, [base])
    assert not loop_detour(south, [base])
