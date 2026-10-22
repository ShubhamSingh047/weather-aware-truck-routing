"""Grid cells covering the corridor around the candidate routes."""

import math
from collections.abc import Sequence

from .geo import LatLon, RouteGeometry, sample_spaced

NICE_STEPS_DEG = (0.1, 0.2, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0)
TARGET_CELLS_ACROSS = 28  # resolution along the longest side of the trip's bounding box
MILES_PER_DEG_LAT = 69.0


def grid_step(geometries: Sequence[RouteGeometry]) -> float:
    lats = [c[0] for g in geometries for c in g.coords]
    lons = [c[1] for g in geometries for c in g.coords]
    mid_lat = (min(lats) + max(lats)) / 2
    span = max(max(lats) - min(lats), (max(lons) - min(lons)) * math.cos(math.radians(mid_lat)))
    raw = span / TARGET_CELLS_ACROSS
    return next((s for s in NICE_STEPS_DEG if s >= raw), NICE_STEPS_DEG[-1])


def fit_corridor(geometries: Sequence[RouteGeometry], max_cells: int) -> tuple[float, list[LatLon]]:
    """Finest grid (starting at `grid_step`) whose corridor stays within `max_cells`."""
    start = NICE_STEPS_DEG.index(grid_step(geometries))
    for step in NICE_STEPS_DEG[start:]:
        cells = corridor_cells(geometries, step)
        if len(cells) <= max_cells:
            break
    return step, cells


def corridor_cells(geometries: Sequence[RouteGeometry], step: float) -> list[LatLon]:
    """Grid cell centres within the corridor radius of any route.

    Cells sit on multiples of `step`, so overlapping trips share cache entries.
    """
    step_miles = step * MILES_PER_DEG_LAT
    radius = max(30.0, 1.25 * step_miles)
    cells: dict[LatLon, None] = {}
    for geometry in geometries:
        for lat, lon in sample_spaced(geometry.coords, geometry.miles, step_miles / 2):
            cos_lat = max(0.2, math.cos(math.radians(lat)))
            reach_lat = math.ceil(radius / (step_miles)) + 1
            reach_lon = math.ceil(radius / (step_miles * cos_lat)) + 1
            base_i, base_j = round(lat / step), round(lon / step)
            for i in range(base_i - reach_lat, base_i + reach_lat + 1):
                for j in range(base_j - reach_lon, base_j + reach_lon + 1):
                    cell = (round(i * step, 4), round(j * step, 4))
                    if cell in cells:
                        continue
                    dy = (cell[0] - lat) * MILES_PER_DEG_LAT
                    dx = (cell[1] - lon) * MILES_PER_DEG_LAT * cos_lat
                    if dx * dx + dy * dy <= radius * radius:
                        cells[cell] = None
    return list(cells)
