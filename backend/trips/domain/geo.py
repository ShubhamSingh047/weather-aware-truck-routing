"""Geometry helpers: polyline decoding, distances and positions along a route."""

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

EARTH_RADIUS_MI = 3958.8
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def decode_polyline(encoded: str, precision: int = 6) -> list[LatLon]:
    """Decode a Google-style encoded polyline (OSRM uses precision 6)."""
    coords: list[LatLon] = []
    index = lat = lon = 0
    factor = 10**precision
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coords.append((lat / factor, lon / factor))
    return coords


def cumulative_miles(coords: Sequence[LatLon]) -> list[float]:
    total = 0.0
    out = [0.0]
    for a, b in zip(coords, coords[1:]):
        total += haversine_miles(a, b)
        out.append(total)
    return out


def _interpolate(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    """Piecewise-linear interpolation; xs must be non-decreasing."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x)
    x0, x1 = xs[i - 1], xs[i]
    if x1 == x0:
        return ys[i]
    t = (x - x0) / (x1 - x0)
    return ys[i - 1] + t * (ys[i] - ys[i - 1])


@dataclass(frozen=True)
class RouteGeometry:
    """A route's shape with cumulative miles and drive seconds at every vertex."""

    coords: list[LatLon]
    miles: list[float]
    seconds: list[float]

    def __post_init__(self):
        if not (len(self.coords) == len(self.miles) == len(self.seconds)) or len(self.coords) < 2:
            raise ValueError("coords, miles and seconds must align and contain at least two points")

    @property
    def length_miles(self) -> float:
        return self.miles[-1]

    @property
    def duration_s(self) -> float:
        return self.seconds[-1]

    @cached_property
    def _lats(self) -> list[float]:
        return [c[0] for c in self.coords]

    @cached_property
    def _lons(self) -> list[float]:
        return [c[1] for c in self.coords]

    def point_at_mile(self, mile: float) -> LatLon:
        return _interpolate(self.miles, self._lats, mile), _interpolate(self.miles, self._lons, mile)

    def seconds_at_mile(self, mile: float) -> float:
        return _interpolate(self.miles, self.seconds, mile)

    def checkpoint_miles(self, interval_miles: float) -> list[float]:
        """Mile 0, every `interval_miles`, and the destination."""
        marks = [i * interval_miles for i in range(int(self.length_miles // interval_miles) + 1)]
        # Avoid a near-duplicate checkpoint right before the destination.
        if self.length_miles - marks[-1] < 0.5 and len(marks) > 1:
            marks.pop()
        marks.append(self.length_miles)
        return marks

    def simplified(self, step_miles: float) -> list[tuple[float, float, float, float]]:
        """(lat, lon, seconds, mile) roughly every `step_miles`, for drawing and animation."""
        out = []
        next_mile = 0.0
        for (lat, lon), mile, sec in zip(self.coords, self.miles, self.seconds):
            if mile >= next_mile:
                out.append((lat, lon, sec, mile))
                next_mile = mile + step_miles
        if out[-1][3] != self.length_miles:
            lat, lon = self.coords[-1]
            out.append((lat, lon, self.seconds[-1], self.length_miles))
        return out


def build_geometry(coords: Sequence[LatLon], segment_seconds: Sequence[float] | None = None,
                   total_seconds: float | None = None) -> RouteGeometry:
    """Build a RouteGeometry.

    Uses per-segment durations when given (len == len(coords) - 1); otherwise
    spreads `total_seconds` over the route in proportion to distance.
    """
    coords = list(coords)
    miles = cumulative_miles(coords)
    if segment_seconds is not None and len(segment_seconds) == len(coords) - 1:
        seconds = [0.0]
        for s in segment_seconds:
            seconds.append(seconds[-1] + max(0.0, s))
    elif total_seconds is not None and miles[-1] > 0:
        seconds = [total_seconds * m / miles[-1] for m in miles]
    else:
        raise ValueError("need segment durations or a total duration")
    return RouteGeometry(coords=coords, miles=miles, seconds=seconds)


def sample_spaced(coords: Sequence[LatLon], miles: Sequence[float], step_miles: float) -> list[LatLon]:
    """Points roughly every `step_miles`, used for cheap route similarity checks."""
    out = []
    next_mile = 0.0
    for coord, mile in zip(coords, miles):
        if mile >= next_mile:
            out.append(coord)
            next_mile = mile + step_miles
    return out


def overlap_ratio(candidate: RouteGeometry, other: RouteGeometry, tolerance_miles: float = 1.0) -> float:
    """Share of `candidate` that runs within `tolerance_miles` of `other`."""
    probe = sample_spaced(candidate.coords, candidate.miles, 5.0)
    reference = sample_spaced(other.coords, other.miles, 1.0)
    if not probe:
        return 0.0
    # Equirectangular distance is plenty accurate at this scale and much cheaper.
    def close(p: LatLon) -> bool:
        cos_lat = math.cos(math.radians(p[0]))
        for q in reference:
            dy = (p[0] - q[0]) * 69.0
            dx = (p[1] - q[1]) * 69.0 * cos_lat
            if dx * dx + dy * dy <= tolerance_miles**2:
                return True
        return False

    return sum(1 for p in probe if close(p)) / len(probe)


def backtrack_ratio(geometry: RouteGeometry, tolerance_miles: float = 0.5, min_gap_miles: float = 10.0) -> float:
    """Share of the route that doubles back over road it already drove.

    Via-point routes sometimes snap the via point onto a side road, producing
    an out-and-back spur. A probe point (every 2 mi) that comes within
    `tolerance_miles` of road driven more than `min_gap_miles` earlier
    (sampled every 0.25 mi) marks such a spur.
    """
    cell = 1.0
    index: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for (lat, lon), mile in zip(*_resample(geometry, 0.25)):
        index.setdefault((int(lat * 69 // cell), int(lon * 69 // cell)), []).append((lat, lon, mile))

    probes = list(zip(*_resample(geometry, 2.0)))
    if len(probes) < 3:
        return 0.0
    hits = 0
    for (lat, lon), mile in probes:
        cos_lat = math.cos(math.radians(lat))
        i, j = int(lat * 69 // cell), int(lon * 69 // cell)
        reach = math.ceil(tolerance_miles / (cell * cos_lat)) + 1
        hits += any(
            mile - q_mile > min_gap_miles
            and ((lat - q_lat) * 69.0) ** 2 + ((lon - q_lon) * 69.0 * cos_lat) ** 2 <= tolerance_miles**2
            for di in (-1, 0, 1)
            for dj in range(-reach, reach + 1)
            for q_lat, q_lon, q_mile in index.get((i + di, j + dj), ())
        )
    return hits / len(probes)


def _resample(geometry: RouteGeometry, step_miles: float) -> tuple[list[LatLon], list[float]]:
    """Points interpolated every `step_miles` along the route, with their miles."""
    miles = [k * step_miles for k in range(int(geometry.length_miles // step_miles) + 1)]
    return [geometry.point_at_mile(m) for m in miles], miles


def _spatial_index(points: Sequence[LatLon], cell_miles: float) -> dict[tuple[int, int], list[LatLon]]:
    index: dict[tuple[int, int], list[LatLon]] = {}
    for lat, lon in points:
        index.setdefault((int(lat * 69 // cell_miles), int(lon * 69 // cell_miles)), []).append((lat, lon))
    return index


def _near(point: LatLon, index: dict[tuple[int, int], list[LatLon]], cell_miles: float, tolerance: float) -> bool:
    lat, lon = point
    cos_lat = math.cos(math.radians(lat))
    i, j = int(lat * 69 // cell_miles), int(lon * 69 // cell_miles)
    reach = max(1, math.ceil(tolerance / (cell_miles * cos_lat)))
    for di in range(-1, 2):
        for dj in range(-reach, reach + 1):
            for q in index.get((i + di, j + dj), ()):
                dy = (lat - q[0]) * 69.0
                dx = (lon - q[1]) * 69.0 * cos_lat
                if dx * dx + dy * dy <= tolerance * tolerance:
                    return True
    return False


def loop_detour(candidate: RouteGeometry, others: Sequence[RouteGeometry], tolerance_miles: float = 1.0,
                min_run_miles: float = 15.0, max_ratio: float = 1.5) -> bool:
    """True if the candidate leaves the other routes only to rejoin them nearby.

    A genuine alternative diverges and rejoins far apart (driven length close
    to the straight-line gap). A loop driven to reach a via point covers many
    miles but rejoins close to where it left.
    """
    cell = max(tolerance_miles, 1.0)
    index = _spatial_index([p for g in others for p in sample_spaced(g.coords, g.miles, 0.5)], cell)
    probe = []
    next_mile = 0.0
    for coord, mile in zip(candidate.coords, candidate.miles):
        if mile >= next_mile:
            probe.append((coord, mile, _near(coord, index, cell, tolerance_miles)))
            next_mile = mile + 2.0

    i = 0
    while i < len(probe):
        if probe[i][2]:
            i += 1
            continue
        start = max(0, i - 1)
        while i < len(probe) and not probe[i][2]:
            i += 1
        end = min(len(probe) - 1, i)
        driven = probe[end][1] - probe[start][1]
        gap = haversine_miles(probe[start][0], probe[end][0])
        if driven >= min_run_miles and driven > max_ratio * max(gap, 1.0):
            return True
    return False
