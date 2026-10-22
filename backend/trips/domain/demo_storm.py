"""A simulated storm laid over the real forecast, for demos when the weather is calm.

The storm is placed on the fastest route where the alternatives are farthest
away, and peaks exactly when that route's truck gets there. Everything
downstream (risk rules, load rules, ranking, heatmap) runs unchanged on the
combined conditions, so the demo exercises the real logic.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .analysis import Conditions, WeatherLookup
from .geo import RouteGeometry, sample_spaced

PEAK_WIND_MPH = 60.0  # core is No Travel for any load
WIND_RADIUS_MI = 70.0  # e-folding distance; ~50 mph at 30 mi, ~29 mph at 60 mi
PEAK_RAIN_IN_HR = 0.8
RAIN_RADIUS_MI = 55.0
LIFETIME_H = 12.0  # e-folding time either side of the peak
DRIFT_MPH = 20.0  # eastward
GUST_FACTOR = 1.3


@dataclass(frozen=True)
class DemoStorm:
    lat: float  # centre at peak
    lon: float
    peak_ts: float

    def centre_at(self, unix_ts: float) -> tuple[float, float]:
        hours = (unix_ts - self.peak_ts) / 3600
        return self.lat, self.lon + DRIFT_MPH * hours / (69.0 * math.cos(math.radians(self.lat)))

    def apply(self, lat: float, lon: float, unix_ts: float, base: Conditions | None) -> Conditions | None:
        """Combine the storm with real conditions: stronger wind wins, rain adds up."""
        if base is None:
            return None
        hours = (unix_ts - self.peak_ts) / 3600
        strength = math.exp(-((hours / LIFETIME_H) ** 2))
        c_lat, c_lon = self.centre_at(unix_ts)
        dy = (lat - c_lat) * 69.0
        dx = (lon - c_lon) * 69.0 * math.cos(math.radians(lat))
        dist2 = dx * dx + dy * dy
        wind = PEAK_WIND_MPH * strength * math.exp(-dist2 / WIND_RADIUS_MI**2)
        rain = PEAK_RAIN_IN_HR * strength * math.exp(-dist2 / RAIN_RADIUS_MI**2)
        return Conditions(
            wind_mph=max(base.wind_mph, wind),
            gust_mph=max(base.gust_mph, wind * GUST_FACTOR),
            rain_in_hr=base.rain_in_hr + rain,
            snow_in_hr=base.snow_in_hr,
        )

    @classmethod
    def on_route(cls, fastest: RouteGeometry, others: Sequence[RouteGeometry], departure_ts: float) -> "DemoStorm":
        """Centre on the middle half of `fastest`, as far from the other routes as possible."""
        reference = [p for g in others for p in sample_spaced(g.coords, g.miles, 5.0)]

        def clearance(mile: float) -> float:
            lat, lon = fastest.point_at_mile(mile)
            if not reference:
                return 0.0
            cos_lat = math.cos(math.radians(lat))
            return min(((lat - q[0]) * 69.0) ** 2 + ((lon - q[1]) * 69.0 * cos_lat) ** 2 for q in reference)

        length = fastest.length_miles
        candidates = [length * f / 20 for f in range(5, 16)]  # 25% .. 75%
        mile = max(candidates, key=clearance)
        lat, lon = fastest.point_at_mile(mile)
        return cls(lat=lat, lon=lon, peak_ts=departure_ts + fastest.seconds_at_mile(mile))


class StormWeather:
    """WeatherLookup that adds a DemoStorm to another lookup."""

    def __init__(self, weather: WeatherLookup, storm: DemoStorm):
        self.weather = weather
        self.storm = storm

    def at(self, lat: float, lon: float, unix_ts: float) -> Conditions | None:
        return self.storm.apply(lat, lon, unix_ts, self.weather.at(lat, lon, unix_ts))
