"""Open-Meteo hourly forecasts, fetched per grid cell and cached across requests.

Budget: Open-Meteo's free tier allows 10,000 calls/day and we assume each
location in a multi-location request costs one call. Snapping lookups to a
grid lets the three (often overlapping) routes and the heatmap share cells,
and the shared cache means a corridor fetched once is free for the next hour.
"""

import logging
import math
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from ..domain.analysis import Conditions
from ..domain.geo import LatLon
from .errors import ProviderError

logger = logging.getLogger(__name__)

HOURLY_VARS = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
# 7 days in total: longer windows are billed as more than one call per location.
PAST_DAYS = 1
FORECAST_DAYS = 6
LOCATIONS_PER_REQUEST = 100
CACHE_VERSION = 1


def snap(lat: float, lon: float, step: float) -> LatLon:
    return round(round(lat / step) * step, 4), round(round(lon / step) * step, 4)


@dataclass(frozen=True)
class HourlySeries:
    """Hourly values starting at `start_ts` (unix seconds, top of the hour, UTC).

    Open-Meteo semantics: wind is the instantaneous value at the timestamp;
    rain and snowfall are the total over the preceding hour.
    """

    start_ts: int
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in: list[float | None]
    snow_in: list[float | None]

    def _value(self, values: list[float | None], index: int) -> float | None:
        return values[index] if 0 <= index < len(values) else None

    def conditions_at(self, unix_ts: float) -> Conditions | None:
        offset_h = (unix_ts - self.start_ts) / 3600
        instant = round(offset_h)  # nearest hourly sample
        hour_ending = math.ceil(offset_h)  # precipitation accumulated over the hour containing ts
        wind = self._value(self.wind_mph, instant)
        gust = self._value(self.gust_mph, instant)
        rain = self._value(self.rain_in, hour_ending)
        snow = self._value(self.snow_in, hour_ending)
        if wind is None or rain is None or snow is None:
            return None
        return Conditions(wind_mph=wind, gust_mph=gust if gust is not None else wind,
                          rain_in_hr=rain, snow_in_hr=snow)


class OpenMeteoWeather:
    """Implements the WeatherLookup protocol for checkpoints snapped to `checkpoint_step`."""

    def __init__(self, session: requests.Session | None = None, checkpoint_step: float = 0.1):
        self.checkpoint_step = checkpoint_step
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = settings.HTTP_USER_AGENT
        self._series: dict[LatLon, HourlySeries] = {}
        self.locations_fetched = 0
        self.locations_from_cache = 0

    # -- WeatherLookup ------------------------------------------------------
    def at(self, lat: float, lon: float, unix_ts: float) -> Conditions | None:
        series = self._series.get(snap(lat, lon, self.checkpoint_step))
        return series.conditions_at(unix_ts) if series else None

    def series(self, cell: LatLon) -> HourlySeries | None:
        return self._series.get(cell)

    # -- Fetching -----------------------------------------------------------
    def prefetch(self, cells: Iterable[LatLon]) -> None:
        wanted = [c for c in dict.fromkeys(cells) if c not in self._series]
        if not wanted:
            return
        bucket = int(time.time() // 3600)  # new forecast data roughly hourly
        keys = {c: f"wx:v{CACHE_VERSION}:{c[0]:.4f}:{c[1]:.4f}:{bucket}" for c in wanted}
        cached = cache.get_many(keys.values())
        missing = []
        for cell, key in keys.items():
            if key in cached:
                self._series[cell] = cached[key]
            else:
                missing.append(cell)
        self.locations_from_cache += len(wanted) - len(missing)
        if not missing:
            return

        chunks = [missing[i:i + LOCATIONS_PER_REQUEST] for i in range(0, len(missing), LOCATIONS_PER_REQUEST)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(self._fetch_chunk, chunks))
        fresh = {}
        for chunk, series_list in zip(chunks, results):
            for cell, series in zip(chunk, series_list):
                self._series[cell] = series
                fresh[keys[cell]] = series
        cache.set_many(fresh, timeout=3600)
        self.locations_fetched += len(missing)

    def _fetch_chunk(self, cells: list[LatLon]) -> list[HourlySeries]:
        params = {
            "latitude": ",".join(f"{c[0]:.4f}" for c in cells),
            "longitude": ",".join(f"{c[1]:.4f}" for c in cells),
            "hourly": ",".join(HOURLY_VARS),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "past_days": PAST_DAYS,
            "forecast_days": FORECAST_DAYS,
        }
        url = f"{settings.OPEN_METEO_BASE_URL}/v1/forecast"
        try:
            response = self.session.get(url, params=params, timeout=20)
        except requests.RequestException as exc:
            raise ProviderError("Weather service is unreachable. Please try again.") from exc
        if response.status_code == 429:
            raise ProviderError("Weather service rate limit reached. Please try again later.")
        if not response.ok:
            logger.warning("Open-Meteo %s: %s", response.status_code, response.text[:300])
            raise ProviderError("Weather service returned an error.")
        try:
            payload = response.json()
            items = payload if isinstance(payload, list) else [payload]
            if len(items) != len(cells):
                raise ProviderError("Weather service returned an unexpected number of locations.")
            return [self._parse(item) for item in items]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.exception("unexpected Open-Meteo response")
            raise ProviderError("Weather service returned an unexpected response.") from exc

    @staticmethod
    def _parse(item: dict) -> HourlySeries:
        hourly = item["hourly"]
        rain = [
            None if r is None else r + (s or 0.0)  # liquid precipitation = rain + showers
            for r, s in zip(hourly["rain"], hourly["showers"])
        ]
        return HourlySeries(
            start_ts=int(hourly["time"][0]),
            wind_mph=hourly["wind_speed_10m"],
            gust_mph=hourly["wind_gusts_10m"],
            rain_in=rain,
            snow_in=hourly["snowfall"],
        )
