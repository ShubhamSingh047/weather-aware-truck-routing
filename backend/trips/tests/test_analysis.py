import pytest

from trips.domain.analysis import Conditions, RouteAnalysis, build_checkpoints, rank_routes
from trips.domain.demo_storm import DemoStorm
from trips.domain.geo import build_geometry, decode_polyline, haversine_miles
from trips.domain.risk import Risk, assess

CALM = Conditions(wind_mph=5, gust_mph=8, rain_in_hr=0, snow_in_hr=0)
HEAVY_RAIN = Conditions(wind_mph=5, gust_mph=8, rain_in_hr=0.6, snow_in_hr=0)  # Severe
MODERATE_WIND = Conditions(wind_mph=30, gust_mph=40, rain_in_hr=0, snow_in_hr=0)


def straight_route(miles: float, hours: float):
    """A due-north route from (35, -100) of roughly `miles` length."""
    end_lat = 35 + miles / 69.09
    return build_geometry([(35.0, -100.0), (end_lat, -100.0)], total_seconds=hours * 3600)


class FixedWeather:
    """Returns conditions by latitude band, recording every lookup time."""

    def __init__(self, default=CALM, bands=()):
        self.default = default
        self.bands = bands  # (min_lat, max_lat, conditions)
        self.lookups = []

    def at(self, lat, lon, unix_ts):
        self.lookups.append(unix_ts)
        for lo, hi, conditions in self.bands:
            if lo <= lat <= hi:
                return conditions
        return self.default


def test_haversine_one_degree_latitude():
    assert haversine_miles((0, 0), (1, 0)) == pytest.approx(69.09, rel=1e-3)


def test_decode_polyline_precision_5_reference():
    # Google's documented example string.
    coords = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision=5)
    assert coords == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


class TestCheckpoints:
    def test_checkpoints_every_interval_plus_destination(self):
        geometry = straight_route(100, 2)
        cps = build_checkpoints(geometry, 0, 25, 10_000, FixedWeather())
        assert [round(c.mile) for c in cps] == [0, 25, 50, 75, round(geometry.length_miles)]

    def test_no_near_duplicate_checkpoint_at_destination(self):
        geometry = straight_route(50.2, 1)
        marks = geometry.checkpoint_miles(25)
        assert len(marks) == 3 and marks[-1] == pytest.approx(geometry.length_miles)

    def test_eta_uses_departure_plus_drive_time(self):
        geometry = straight_route(100, 2)  # 50 mph
        weather = FixedWeather()
        cps = build_checkpoints(geometry, departure_ts=1_000_000, interval_miles=50,
                                load_lbs=10_000, weather=weather)
        assert cps[1].eta == pytest.approx(1_000_000 + 3600, abs=60)
        assert weather.lookups == [cp.eta for cp in cps]

    def test_attributed_miles_cover_route_exactly_once(self):
        geometry = straight_route(87, 2)
        cps = build_checkpoints(geometry, 0, 10, 10_000, FixedWeather())
        assert sum(cp.covered_miles for cp in cps) == pytest.approx(geometry.length_miles)
        for a, b in zip(cps, cps[1:]):
            assert a.covers[1] == pytest.approx(b.covers[0])

    def test_missing_weather_counts_as_unknown_miles(self):
        geometry = straight_route(50, 1)
        weather = FixedWeather(default=None)
        analysis = RouteAnalysis("A", geometry, build_checkpoints(geometry, 0, 25, 10_000, weather))
        assert analysis.unknown_miles == pytest.approx(geometry.length_miles)
        assert analysis.average_risk == 0


def analyse(route_id, miles, hours, weather):
    geometry = straight_route(miles, hours)
    return RouteAnalysis(route_id, geometry, build_checkpoints(geometry, 0, 10, 10_000, weather))


class TestRanking:
    def test_severe_miles_beat_travel_time(self):
        risky_fast = analyse("A", 100, 1.5, FixedWeather(bands=[(35.5, 36.0, HEAVY_RAIN)]))
        safe_slow = analyse("B", 100, 3, FixedWeather())
        ranked, reason = rank_routes([risky_fast, safe_slow])
        assert [r.route_id for r in ranked] == ["B", "A"]
        assert risky_fast.miles_by_level[Risk.SEVERE] > 0
        assert "Severe miles" in reason
        assert "Route A is faster (1.5 h) but has" in reason

    def test_average_risk_breaks_tie_on_severe_and_high(self):
        windy = analyse("A", 100, 1.5, FixedWeather(default=MODERATE_WIND))
        calm = analyse("B", 100, 2.0, FixedWeather())
        ranked, reason = rank_routes([windy, calm])
        assert ranked[0].route_id == "B"
        assert "average risk" in reason

    def test_travel_time_is_last_tiebreaker(self):
        slow = analyse("A", 100, 3, FixedWeather())
        fast = analyse("B", 100, 2, FixedWeather())
        ranked, reason = rank_routes([slow, fast])
        assert ranked[0].route_id == "B"
        assert "travel time" in reason
        assert "is faster" not in reason  # the winner is the fastest route

    def test_no_travel_ranks_below_severe(self):
        no_travel = analyse("A", 100, 2, FixedWeather(bands=[(35.5, 35.6, Conditions(60, 70, 0, 0))]))
        severe = analyse("B", 100, 2, FixedWeather(default=HEAVY_RAIN))
        ranked, _ = rank_routes([no_travel, severe])
        assert ranked[0].route_id == "B"

    def test_average_risk_is_mile_weighted(self):
        half_moderate = analyse("A", 100, 2, FixedWeather(bands=[(35.0, 35.0 + 50 / 69.09, MODERATE_WIND)]))
        assert half_moderate.average_risk == pytest.approx(0.5, abs=0.06)


class TestDemoStorm:
    def test_core_is_no_travel_and_fades_with_distance_and_time(self):
        storm = DemoStorm(lat=40.0, lon=-100.0, peak_ts=1_000_000)
        core = storm.apply(40.0, -100.0, 1_000_000, CALM)
        far = storm.apply(42.0, -100.0, 1_000_000, CALM)  # ~138 mi north
        later = storm.apply(40.0, -100.0, 1_000_000 + 48 * 3600, CALM)
        assert assess(core.wind_mph, core.rain_in_hr, core.snow_in_hr, 10_000).level == Risk.NO_TRAVEL
        assert assess(far.wind_mph, far.rain_in_hr, far.snow_in_hr, 10_000).level == Risk.LOW
        assert later.wind_mph == pytest.approx(CALM.wind_mph)

    def test_storm_never_weakens_real_weather_and_keeps_missing_data_missing(self):
        storm = DemoStorm(lat=40.0, lon=-100.0, peak_ts=0)
        windy = Conditions(wind_mph=70, gust_mph=80, rain_in_hr=0.2, snow_in_hr=1.0)
        result = storm.apply(45.0, -90.0, 0, windy)
        assert result.wind_mph == 70 and result.snow_in_hr >= 1.0 and result.rain_in_hr >= 0.2
        assert storm.apply(40.0, -100.0, 0, None) is None

    def test_snow_falls_on_the_cold_north_side_rain_on_the_south(self):
        storm = DemoStorm(lat=40.0, lon=-100.0, peak_ts=0)
        north = storm.apply(40.5, -100.0, 0, CALM)  # ~35 mi north
        south = storm.apply(39.5, -100.0, 0, CALM)
        assert north.snow_in_hr > 0.5 and north.rain_in_hr < south.rain_in_hr
        assert south.snow_in_hr < 0.05 and south.rain_in_hr > 0.2

    def test_storm_sits_on_fastest_route_away_from_alternatives(self):
        fastest = straight_route(300, 5)
        far_away = build_geometry([(35.0, -95.0), (39.0, -95.0)], total_seconds=6 * 3600)
        storm = DemoStorm.on_route(fastest, [far_away], departure_ts=0)
        mile = (storm.lat - 35.0) * 69.09
        assert 0.25 * 300 <= mile <= 0.75 * 300
        assert storm.lon == pytest.approx(-100.0)
        assert storm.peak_ts == pytest.approx(fastest.seconds_at_mile(mile), abs=60)
