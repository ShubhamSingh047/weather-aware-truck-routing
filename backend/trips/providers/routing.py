"""Route options from TomTom (truck profile) or OSRM (free fallback, car profile).

Routing APIs often return fewer than three genuinely different routes. When
that happens we ask for extra routes forced through a via point (an
interstate town off the routes found so far, or failing that a point offset
to either side of the trip) and keep only the ones that are real choices.
"""

import logging
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

import requests
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.debug import sensitive_variables

from ..domain.geo import (
    LatLon,
    RouteGeometry,
    backtrack_ratio,
    build_geometry,
    haversine_miles,
    loop_detour,
    overlap_ratio,
    sample_spaced,
)
from .errors import ProviderError
from .us_cities import US_VIA_CITIES

logger = logging.getLogger(__name__)

TARGET_ROUTES = 3
MAX_OVERLAP = 0.8  # a route sharing more than this with another adds little choice
MAX_DETOUR = 1.5  # ignore alternatives this much longer (distance or time) than the best route
MAX_BACKTRACK = 0.02  # via-point routes that double back on themselves are not real options
MAX_CITY_ATTEMPTS = 6
VIA_BATCH = 3  # via routes requested in parallel
CITY_MAX_DETOUR = 1.3  # straight-line detour through the town vs the direct line
CITY_MIN_OFF_ROUTE_MI = 25  # towns this close to a chosen route would not change it
VIA_OFFSETS = (0.12, -0.12, 0.25)  # fallback: fraction of trip length beside the midpoint
OSRM_TRUCK_MAX_MPH = 65.0  # OSRM's car profile drives faster than a loaded truck may
LBS_TO_KG = 0.45359237


@dataclass(frozen=True)
class RouteOption:
    geometry: RouteGeometry
    roads: str  # main roads, e.g. "I-80, I-76"
    source: str
    via: str = ""  # town the route was forced through, if any


class RoutingProvider(Protocol):
    name: str

    def fetch(self, points: list[LatLon], departure_ts: float, load_lbs: float,
              alternatives: int) -> list[RouteOption]: ...


def _get_json(url: str, params: dict, service: str) -> dict:
    try:
        response = requests.get(url, params=params, headers={"User-Agent": settings.HTTP_USER_AGENT}, timeout=25)
    except requests.RequestException as exc:
        raise ProviderError(f"{service} is unreachable. Please try again.") from exc
    if response.status_code == 429:
        raise ProviderError(f"{service} rate limit reached. Please try again shortly.")
    if response.status_code >= 500:
        raise ProviderError(f"{service} is having problems. Please try again.")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"{service} returned an unreadable response.") from exc


def _parse_all(parse, routes: list[dict]) -> list[RouteOption]:
    try:
        return [parse(route) for route in routes]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.exception("unexpected routing response")
        raise ProviderError("Routing service returned an unexpected response.") from exc


class OsrmProvider:
    name = "osrm"

    def fetch(self, points, departure_ts, load_lbs, alternatives):
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
        data = _get_json(
            f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}",
            {
                "alternatives": str(alternatives) if alternatives and len(points) == 2 else "false",
                "overview": "full",
                "geometries": "geojson",
                "annotations": "duration",
                "steps": "true",  # needed for road names
            },
            "Routing service",
        )
        if data.get("code") != "Ok":
            if data.get("code") in {"NoRoute", "NoSegment"}:
                return []
            raise ProviderError(data.get("message") or "Routing service returned an error.")
        return _parse_all(self._parse, data["routes"])

    @staticmethod
    def _parse(route: dict) -> RouteOption:
        coords = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
        durations = [d for leg in route["legs"] for d in leg["annotation"]["duration"]]
        if len(durations) == len(coords) - 1:
            # Cap speed at a realistic truck speed, segment by segment.
            durations = [
                max(d, haversine_miles(a, b) / OSRM_TRUCK_MAX_MPH * 3600)
                for d, a, b in zip(durations, coords, coords[1:])
            ]
            geometry = build_geometry(coords, segment_seconds=durations)
        else:
            geometry = build_geometry(coords, total_seconds=route["duration"])
        distance_by_road: Counter[str] = Counter()
        for leg in route["legs"]:
            for step in leg.get("steps", []):
                ref = (step.get("ref") or "").split(";")[0].strip()
                if ref:
                    distance_by_road[ref] += step["distance"]
        roads = ", ".join(road for road, _ in distance_by_road.most_common(2))
        return RouteOption(geometry=geometry, roads=roads, source="osrm")


class TomTomProvider:
    name = "tomtom"

    @sensitive_variables("params")  # holds the API key; keep it out of error reports
    def fetch(self, points, departure_ts, load_lbs, alternatives):
        path = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in points)
        params = {
            "key": settings.TOMTOM_API_KEY,
            "travelMode": "truck",
            "vehicleCommercial": "true",
            "vehicleWeight": round(load_lbs * LBS_TO_KG),
            "routeType": "fastest",
            "traffic": "true",
            "routeRepresentation": "polyline",
            "instructionsType": "coded",
        }
        if alternatives and len(points) == 2:
            params["maxAlternatives"] = alternatives
        if departure_ts > datetime.now(UTC).timestamp() + 60:
            params["departAt"] = datetime.fromtimestamp(departure_ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = _get_json(f"https://api.tomtom.com/routing/1/calculateRoute/{path}/json", params, "Routing service")
        if "error" in data or "detailedError" in data:
            message = (data.get("error") or data.get("detailedError") or {}).get("message", "")
            if "NO_ROUTE_FOUND" in str(data) or "no route" in message.lower():
                return []
            raise ProviderError(message or "Routing service returned an error.")
        return _parse_all(self._parse, data.get("routes", []))

    @staticmethod
    def _parse(route: dict) -> RouteOption:
        coords = [(p["latitude"], p["longitude"]) for leg in route["legs"] for p in leg["points"]]
        total_s = route["summary"]["travelTimeInSeconds"]
        instructions = route.get("guidance", {}).get("instructions", [])
        geometry = build_geometry(coords, total_seconds=total_s)
        # Instructions carry the real drive time to their point; use them as
        # anchors so slow stretches (cities, traffic) get their actual timing.
        anchors = sorted({(geometry.miles[i["pointIndex"]], float(i["travelTimeInSeconds"]))
                          for i in instructions if 0 <= i.get("pointIndex", -1) < len(coords)})
        if anchors:
            anchor_miles = [0.0] + [m for m, _ in anchors] + [geometry.length_miles]
            anchor_secs = [0.0] + [s for _, s in anchors] + [float(total_s)]
            seconds = []
            j = 0
            for mile in geometry.miles:
                while j < len(anchor_miles) - 2 and anchor_miles[j + 1] < mile:
                    j += 1
                m0, m1 = anchor_miles[j], anchor_miles[j + 1]
                s0, s1 = anchor_secs[j], anchor_secs[j + 1]
                t = 0.0 if m1 == m0 else (mile - m0) / (m1 - m0)
                seconds.append(max(seconds[-1] if seconds else 0.0, s0 + t * (s1 - s0)))
            geometry = RouteGeometry(coords=geometry.coords, miles=geometry.miles, seconds=seconds)
        return RouteOption(geometry=geometry, roads=TomTomProvider._main_roads(instructions), source="tomtom")

    @staticmethod
    def _main_roads(instructions: list[dict]) -> str:
        distance_by_road: Counter[str] = Counter()
        for current, nxt in zip(instructions, instructions[1:]):
            for road in current.get("roadNumbers", [])[:1]:
                distance_by_road[road] += nxt["routeOffsetInMeters"] - current["routeOffsetInMeters"]
        return ", ".join(road for road, _ in distance_by_road.most_common(2))


def default_provider() -> RoutingProvider:
    return TomTomProvider() if settings.TOMTOM_API_KEY else OsrmProvider()


def _via_point(origin: LatLon, destination: LatLon, fraction: float) -> LatLon:
    """A point beside the trip's midpoint, offset perpendicular to the straight line."""
    mid_lat = (origin[0] + destination[0]) / 2
    cos_lat = math.cos(math.radians(mid_lat))
    dx = (destination[1] - origin[1]) * cos_lat
    dy = destination[0] - origin[0]
    return mid_lat - dx * fraction, (origin[1] + destination[1]) / 2 + dy * fraction / cos_lat


def _via_cities(origin: LatLon, destination: LatLon, routes: list[RouteGeometry],
                tried: set[str], limit: int) -> list[tuple[str, float, float]]:
    """Towns with the smallest detour that lie well away from every chosen route."""
    direct = haversine_miles(origin, destination)
    route_points = [p for g in routes for p in sample_spaced(g.coords, g.miles, 3.0)]

    def off_route(lat: float, lon: float) -> bool:
        cos_lat = math.cos(math.radians(lat))
        limit = CITY_MIN_OFF_ROUTE_MI**2
        return all(((lat - p[0]) * 69.0) ** 2 + ((lon - p[1]) * 69.0 * cos_lat) ** 2 > limit for p in route_points)

    candidates = []
    for name, lat, lon in US_VIA_CITIES:
        if name in tried:
            continue
        to_city, from_city = haversine_miles(origin, (lat, lon)), haversine_miles((lat, lon), destination)
        # Skip towns at either end of the trip: they can't change the route much.
        if min(to_city, from_city) < 0.15 * direct:
            continue
        detour = (to_city + from_city) / direct
        if detour <= CITY_MAX_DETOUR:
            candidates.append((detour, name, lat, lon))
    picked = []
    for _, name, lat, lon in sorted(candidates):
        if len(picked) == limit:
            break
        if off_route(lat, lon):
            picked.append((name, lat, lon))
    return picked


def _is_distinct(candidate: RouteOption, chosen: list[RouteOption]) -> bool:
    """A real alternative: not much longer, mostly on other roads, and no loops."""
    shortest = min(r.geometry.length_miles for r in chosen)
    fastest = min(r.geometry.duration_s for r in chosen)
    if candidate.geometry.length_miles > shortest * MAX_DETOUR or candidate.geometry.duration_s > fastest * MAX_DETOUR:
        return False
    if any(overlap_ratio(candidate.geometry, r.geometry) >= MAX_OVERLAP for r in chosen):
        return False
    return not loop_detour(candidate.geometry, [r.geometry for r in chosen])


def route_options(origin: LatLon, destination: LatLon, departure_ts: float, load_lbs: float,
                  provider: RoutingProvider | None = None) -> list[RouteOption]:
    provider = provider or default_provider()
    # TomTom results depend on load and departure time; OSRM's don't.
    key_parts = [provider.name, f"{origin[0]:.4f},{origin[1]:.4f}", f"{destination[0]:.4f},{destination[1]:.4f}"]
    if provider.name == "tomtom":
        key_parts += [str(round(load_lbs, -3)), str(int(departure_ts // 3600))]
    key = "routes:v2:" + ":".join(key_parts)
    if (hit := cache.get(key)) is not None:
        return hit

    options = provider.fetch([origin, destination], departure_ts, load_lbs, alternatives=TARGET_ROUTES - 1)
    if not options:
        raise ProviderError("No drivable route found between these places.")
    chosen = [options[0]]
    for option in options[1:]:
        if len(chosen) < TARGET_ROUTES and _is_distinct(option, chosen):
            chosen.append(option)

    def fetch_via(via: LatLon) -> RouteOption | None:
        try:
            extra = provider.fetch([origin, via, destination], departure_ts, load_lbs, alternatives=0)
        except ProviderError:
            logger.info("via route through %s failed", via)
            return None
        return extra[0] if extra else None

    def consider(candidates: list[tuple[str, LatLon]]) -> None:
        # Fetch a small batch in parallel, then accept in order of preference.
        with ThreadPoolExecutor(max_workers=VIA_BATCH) as pool:
            results = list(pool.map(fetch_via, [via for _, via in candidates]))
        for (label, _), option in zip(candidates, results):
            if len(chosen) >= TARGET_ROUTES:
                return
            if option and backtrack_ratio(option.geometry) <= MAX_BACKTRACK and _is_distinct(option, chosen):
                chosen.append(replace(option, via=label))

    tried: set[str] = set()
    while len(chosen) < TARGET_ROUTES and len(tried) < MAX_CITY_ATTEMPTS:
        cities = _via_cities(origin, destination, [r.geometry for r in chosen], tried,
                             limit=min(VIA_BATCH, MAX_CITY_ATTEMPTS - len(tried)))
        if not cities:
            break
        tried.update(name for name, _, _ in cities)
        consider([(name, (lat, lon)) for name, lat, lon in cities])

    if len(chosen) < TARGET_ROUTES:
        consider([("", _via_point(origin, destination, f)) for f in VIA_OFFSETS[:VIA_BATCH]])

    cache.set(key, chosen, timeout=6 * 3600)
    return chosen
