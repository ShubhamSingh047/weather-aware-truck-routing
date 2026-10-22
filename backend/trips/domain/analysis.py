"""Turn a route + departure time + weather into checkpoints, risk miles and a ranking.

Mile attribution: each checkpoint represents the stretch of road nearest to it,
i.e. from the midpoint with the previous checkpoint to the midpoint with the
next one. Every mile of the route is therefore counted exactly once.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from .geo import RouteGeometry
from .risk import Risk, RiskAssessment, assess


@dataclass(frozen=True)
class Conditions:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


class WeatherLookup(Protocol):
    def at(self, lat: float, lon: float, unix_ts: float) -> Conditions | None: ...


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    lat: float
    lon: float
    eta: float  # unix seconds
    covers: tuple[float, float]  # route miles attributed to this checkpoint
    conditions: Conditions | None
    risk: RiskAssessment | None

    @property
    def covered_miles(self) -> float:
        return self.covers[1] - self.covers[0]


@dataclass
class RouteAnalysis:
    route_id: str
    geometry: RouteGeometry
    checkpoints: list[Checkpoint]
    miles_by_level: dict[Risk, float] = field(init=False)
    unknown_miles: float = field(init=False)
    average_risk: float = field(init=False)

    def __post_init__(self):
        self.miles_by_level = {level: 0.0 for level in Risk}
        self.unknown_miles = 0.0
        weighted = 0.0
        for cp in self.checkpoints:
            if cp.risk is None:
                self.unknown_miles += cp.covered_miles
                continue
            self.miles_by_level[cp.risk.level] += cp.covered_miles
            weighted += int(cp.risk.level) * cp.covered_miles
        known = self.geometry.length_miles - self.unknown_miles
        self.average_risk = weighted / known if known > 0 else 0.0

    @property
    def duration_s(self) -> float:
        return self.geometry.duration_s

    @property
    def length_miles(self) -> float:
        return self.geometry.length_miles

    @property
    def worst_level(self) -> Risk | None:
        levels = [cp.risk.level for cp in self.checkpoints if cp.risk]
        return max(levels) if levels else None

    def sort_key(self) -> tuple:
        """Assessment order: Severe miles, High miles, average risk, travel time.

        No Travel miles are not in the brief's list; they are ranked ahead of
        Severe miles since they are strictly worse. Values are rounded so that
        float noise never decides between two otherwise equal routes.
        """
        return (
            round(self.miles_by_level[Risk.NO_TRAVEL], 1),
            round(self.miles_by_level[Risk.SEVERE], 1),
            round(self.miles_by_level[Risk.HIGH], 1),
            round(self.average_risk, 3),
            round(self.duration_s),
        )


def build_checkpoints(geometry: RouteGeometry, departure_ts: float, interval_miles: float,
                      load_lbs: float, weather: WeatherLookup) -> list[Checkpoint]:
    marks = geometry.checkpoint_miles(interval_miles)
    checkpoints = []
    for i, mile in enumerate(marks):
        start = 0.0 if i == 0 else (marks[i - 1] + mile) / 2
        end = geometry.length_miles if i == len(marks) - 1 else (mile + marks[i + 1]) / 2
        lat, lon = geometry.point_at_mile(mile)
        eta = departure_ts + geometry.seconds_at_mile(mile)
        conditions = weather.at(lat, lon, eta)
        risk = (
            assess(conditions.wind_mph, conditions.rain_in_hr, conditions.snow_in_hr, load_lbs)
            if conditions
            else None
        )
        checkpoints.append(Checkpoint(mile, lat, lon, eta, (start, end), conditions, risk))
    return checkpoints


# (name, headline when this criterion decides, value, unit) in sort_key order
CRITERIA = (
    ("No Travel miles", "Fewest No Travel miles", lambda r: r.miles_by_level[Risk.NO_TRAVEL], "mi"),
    ("Severe miles", "Fewest Severe miles", lambda r: r.miles_by_level[Risk.SEVERE], "mi"),
    ("High miles", "Fewest High miles", lambda r: r.miles_by_level[Risk.HIGH], "mi"),
    ("average risk", "Lowest average risk", lambda r: r.average_risk, "score"),
    ("travel time", "Shortest travel time", lambda r: r.duration_s / 3600, "h"),
)


def _describe(value: float, name: str, unit: str) -> str:
    return f"an {name} of {value:.2f}" if unit == "score" else f"{value:.0f} {name}"


def rank_routes(analyses: Sequence[RouteAnalysis]) -> tuple[list[RouteAnalysis], str]:
    """Return routes best-first and a short explanation of the choice."""
    ranked = sorted(analyses, key=RouteAnalysis.sort_key)
    if len(ranked) < 2:
        return ranked, "Only one route was available."
    best, runner_up = ranked[0], ranked[1]
    reason = "Routes are equivalent on every criterion; picked the first."
    for position, (_, headline, value, unit) in enumerate(CRITERIA):
        if best.sort_key()[position] != runner_up.sort_key()[position]:
            fmt = "{:.3f}" if unit == "score" else "{:.1f}"
            suffix = "" if unit == "score" else f" {unit}"
            reason = (
                f"{headline}: {fmt.format(value(best))}{suffix} "
                f"vs {fmt.format(value(runner_up))}{suffix} on the next-best route."
            )
            if position > 0:
                tied = ", ".join(c[0] for c in CRITERIA[:position])
                reason += f" Tied on {tied}."
            break

    # Make the risk/time trade-off explicit when the quickest route lost on risk.
    fastest = min(analyses, key=lambda r: r.duration_s)
    if fastest is not best:
        for position, (name, _, value, unit) in enumerate(CRITERIA[:-1]):
            if best.sort_key()[position] < fastest.sort_key()[position]:
                reason += (
                    f" Route {fastest.route_id} is faster ({fastest.duration_s / 3600:.1f} h) but has "
                    f"{_describe(value(fastest), name, unit)} vs {value(best):.{2 if unit == 'score' else 0}f}."
                )
                break
    return ranked, reason
