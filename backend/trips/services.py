"""Plan a trip: routes -> checkpoints -> weather -> risk -> recommendation + heatmap."""

import math
import time
from dataclasses import dataclass

from .domain.analysis import Checkpoint, RouteAnalysis, WeatherLookup, build_checkpoints, rank_routes
from .domain.demo_storm import DemoStorm, StormWeather
from .domain.geo import LatLon
from .domain.heatmap import fit_corridor
from .domain.risk import Risk, assess
from .providers.routing import RouteOption, route_options
from .providers.weather import OpenMeteoWeather, snap

MAX_TIMELINE_HOURS = 96  # the timeline runs until the last truck arrives, up to this
ROUTE_LABELS = "ABC"

# Weather budget per request (locations). Open-Meteo's free tier allows 600
# calls/minute and 10,000/day; very long trips get a coarser grid rather than
# blowing through the limit. Cached cells don't count against it.
MAX_CHECKPOINT_CELLS = 250
MAX_HEATMAP_CELLS = 220
CHECKPOINT_STEPS_DEG = (0.1, 0.2, 0.25, 0.5)


@dataclass(frozen=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    departure_ts: float
    load_lbs: float
    interval_miles: int
    demo_storm: bool = False  # overlay a simulated storm on the real forecast


def plan_trip(req: TripRequest, weather: OpenMeteoWeather | None = None) -> dict:
    started = time.perf_counter()
    weather = weather or OpenMeteoWeather()
    options = sorted(route_options(req.origin, req.destination, req.departure_ts, req.load_lbs),
                     key=lambda o: o.geometry.duration_s)
    geometries = [o.geometry for o in options]

    step, heat_cells = fit_corridor(geometries, MAX_HEATMAP_CELLS)
    weather.checkpoint_step, checkpoint_cells = _fit_checkpoint_cells(geometries, req.interval_miles)
    weather.prefetch(checkpoint_cells + heat_cells)

    storm = DemoStorm.on_route(geometries[0], geometries[1:], req.departure_ts) if req.demo_storm else None
    lookup: WeatherLookup = StormWeather(weather, storm) if storm else weather

    analyses = [
        RouteAnalysis(
            route_id=ROUTE_LABELS[i],
            geometry=option.geometry,
            checkpoints=build_checkpoints(option.geometry, req.departure_ts, req.interval_miles,
                                          req.load_lbs, lookup),
        )
        for i, option in enumerate(options)
    ]
    ranked, reason = rank_routes(analyses)
    recommended = ranked[0].route_id
    rank_of = {a.route_id: i + 1 for i, a in enumerate(ranked)}

    return {
        "departure_ts": req.departure_ts,
        "load_lbs": req.load_lbs,
        "interval_miles": req.interval_miles,
        "recommended_route_id": recommended,
        "recommendation_reason": reason,
        "routes": [
            _serialize_route(a, o, rank_of[a.route_id], a.route_id == recommended)
            for a, o in zip(analyses, options)
        ],
        "heatmap": _heatmap(weather, heat_cells, step, req, storm, _timeline_hours(options)),
        "demo_storm": (
            {"lat": round(storm.lat, 4), "lon": round(storm.lon, 4), "peak_ts": round(storm.peak_ts)}
            if storm else None
        ),
        "meta": {
            "routing_source": options[0].source,
            "weather_source": "open-meteo",
            "checkpoint_grid_deg": weather.checkpoint_step,
            "weather_locations_fetched": weather.locations_fetched,
            "weather_locations_cached": weather.locations_from_cache,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        },
    }


def _fit_checkpoint_cells(geometries, interval_miles: int) -> tuple[float, list[LatLon]]:
    positions = [g.point_at_mile(mile) for g in geometries for mile in g.checkpoint_miles(interval_miles)]
    for step in CHECKPOINT_STEPS_DEG:
        cells = list(dict.fromkeys(snap(lat, lon, step) for lat, lon in positions))
        if len(cells) <= MAX_CHECKPOINT_CELLS:
            break
    return step, cells


def _serialize_checkpoint(cp: Checkpoint) -> dict:
    c = cp.conditions
    return {
        "mile": round(cp.mile, 1),
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "eta_ts": round(cp.eta),
        "covers": [round(cp.covers[0], 2), round(cp.covers[1], 2)],
        "level": cp.risk.level.name if cp.risk else None,
        "drivers": cp.risk.drivers if cp.risk else [],
        "wind_mph": round(c.wind_mph, 1) if c else None,
        "gust_mph": round(c.gust_mph, 1) if c else None,
        "rain_in_hr": round(c.rain_in_hr, 3) if c else None,
        "snow_in_hr": round(c.snow_in_hr, 3) if c else None,
    }


def _serialize_route(analysis: RouteAnalysis, option: RouteOption, rank: int, recommended: bool) -> dict:
    g = analysis.geometry
    return {
        "id": analysis.route_id,
        "rank": rank,
        "recommended": recommended,
        "roads": option.roads,
        "via": option.via,
        "distance_miles": round(g.length_miles, 1),
        "duration_s": round(g.duration_s),
        "average_risk": round(analysis.average_risk, 3),
        "worst_level": analysis.worst_level.name if analysis.worst_level is not None else None,
        "miles_by_level": {level.name: round(miles, 1) for level, miles in analysis.miles_by_level.items()},
        "unknown_miles": round(analysis.unknown_miles, 1),
        # [lat, lon, seconds from departure, mile] about every mile: drawing + truck animation
        "path": [[round(lat, 5), round(lon, 5), round(sec), round(mile, 2)]
                 for lat, lon, sec, mile in g.simplified(1.0)],
        "checkpoints": [_serialize_checkpoint(cp) for cp in analysis.checkpoints],
    }


def _timeline_hours(options: list[RouteOption]) -> int:
    """Whole hours from departure until the slowest route's truck arrives."""
    slowest = max(o.geometry.duration_s for o in options)
    return max(1, min(MAX_TIMELINE_HOURS, math.ceil(slowest / 3600)))


def _heatmap(weather: OpenMeteoWeather, cells: list[LatLon], step: float, req: TripRequest,
             storm: DemoStorm | None, hours: int) -> dict:
    """Hourly frames from the departure hour: columnar arrays, frame-major.

    Each value array has hours + 1 frames x len(cells) entries; null
    marks a missing forecast value.
    """
    start_ts = math.floor(req.departure_ts / 3600) * 3600
    frames = hours + 1
    risk, wind, rain, snow = [], [], [], []
    series_by_cell = [weather.series(cell) for cell in cells]
    for frame in range(frames):
        ts = start_ts + frame * 3600
        for cell, series in zip(cells, series_by_cell):
            c = series.conditions_at(ts) if series else None
            if storm:
                c = storm.apply(cell[0], cell[1], ts, c)
            if c is None:
                for column in (risk, wind, rain, snow):
                    column.append(None)
                continue
            risk.append(int(assess(c.wind_mph, c.rain_in_hr, c.snow_in_hr, req.load_lbs).level))
            wind.append(round(c.wind_mph, 1))
            rain.append(round(c.rain_in_hr, 3))
            snow.append(round(c.snow_in_hr, 3))
    return {
        "start_ts": start_ts,
        "frames": frames,
        "step_deg": step,
        "cells": [[lat, lon] for lat, lon in cells],
        "risk": risk,
        "wind_mph": wind,
        "rain_in_hr": rain,
        "snow_in_hr": snow,
        "risk_levels": [level.name for level in Risk],
    }
