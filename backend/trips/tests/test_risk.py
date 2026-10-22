import pytest

from trips.domain.risk import Risk, assess, classify_rain, classify_snow, classify_wind

LIGHT = 10_000


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, Risk.LOW),
        (24.9, Risk.LOW),
        (25, Risk.MODERATE),
        (34.9, Risk.MODERATE),
        (35, Risk.HIGH),
        (44.9, Risk.HIGH),
        (45, Risk.SEVERE),
        (54.9, Risk.SEVERE),
        (55, Risk.NO_TRAVEL),
        (80, Risk.NO_TRAVEL),
    ],
)
def test_wind_bands_for_light_load(mph, expected):
    assert classify_wind(mph, LIGHT) == expected


@pytest.mark.parametrize(
    ("inches", "expected"),
    [
        (0, Risk.LOW),
        (0.099, Risk.LOW),
        (0.10, Risk.MODERATE),
        (0.249, Risk.MODERATE),
        (0.25, Risk.HIGH),
        (0.499, Risk.HIGH),
        (0.50, Risk.SEVERE),
        (1.00, Risk.SEVERE),  # "0.50–1.00" is Severe, No Travel starts above 1.00
        (1.001, Risk.NO_TRAVEL),
    ],
)
def test_rain_bands(inches, expected):
    assert classify_rain(inches) == expected


@pytest.mark.parametrize(
    ("inches", "expected"),
    [
        (0.49, Risk.LOW),
        (0.5, Risk.MODERATE),
        (1.0, Risk.HIGH),
        (2.0, Risk.SEVERE),
        (3.0, Risk.SEVERE),
        (3.01, Risk.NO_TRAVEL),
    ],
)
def test_snow_bands(inches, expected):
    assert classify_snow(inches) == expected


class TestLoadRules:
    def test_55_mph_is_no_travel_for_any_load(self):
        assert classify_wind(55, 0) == Risk.NO_TRAVEL

    def test_severe_wind_with_load_over_30k_is_no_travel(self):
        assert classify_wind(45, 30_001) == Risk.NO_TRAVEL
        assert classify_wind(54.9, 45_000) == Risk.NO_TRAVEL

    def test_severe_wind_at_exactly_30k_stays_severe(self):
        assert classify_wind(50, 30_000) == Risk.SEVERE

    def test_high_wind_with_load_over_40k_is_severe(self):
        assert classify_wind(35, 40_001) == Risk.SEVERE
        assert classify_wind(44.9, 50_000) == Risk.SEVERE

    def test_high_wind_with_load_between_30k_and_40k_stays_high(self):
        assert classify_wind(40, 35_000) == Risk.HIGH
        assert classify_wind(40, 40_000) == Risk.HIGH

    def test_load_does_not_change_moderate_wind(self):
        assert classify_wind(30, 80_000) == Risk.MODERATE


class TestAssess:
    def test_overall_level_is_worst_condition(self):
        result = assess(wind_mph=10, rain_in_hr=0.3, snow_in_hr=1.5, load_lbs=LIGHT)
        assert result.level == Risk.HIGH
        assert sorted(result.drivers) == ["rain", "snow"]

    def test_load_adjusted_wind_drives_level(self):
        result = assess(wind_mph=40, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=42_000)
        assert result.level == Risk.SEVERE
        assert result.drivers == ["wind"]

    def test_calm_weather_has_no_drivers(self):
        result = assess(wind_mph=5, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=LIGHT)
        assert result.level == Risk.LOW
        assert result.drivers == []
