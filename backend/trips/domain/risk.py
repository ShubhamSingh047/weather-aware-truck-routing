"""Weather risk classification, straight from the assessment's risk and load rules.

Band edges: each band includes its lower bound ("25–34 mph" means 25 <= w < 35).
The top band follows the wording of the table: wind is No Travel at >= 55 mph,
while rain and snow are No Travel only when strictly above 1.00 / 3.0 in/hr.
"""

from dataclasses import dataclass
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


# Lower bound (inclusive) for MODERATE, HIGH and SEVERE.
WIND_MPH = (25.0, 35.0, 45.0)
RAIN_IN_HR = (0.10, 0.25, 0.50)
SNOW_IN_HR = (0.5, 1.0, 2.0)

WIND_NO_TRAVEL_MPH = 55.0  # inclusive
RAIN_NO_TRAVEL_IN_HR = 1.00  # exclusive
SNOW_NO_TRAVEL_IN_HR = 3.0  # exclusive

# Load rules
HEAVY_LOAD_NO_TRAVEL_LBS = 30_000  # 45–54 mph and load above this -> No Travel
HEAVY_LOAD_SEVERE_LBS = 40_000  # 35–44 mph and load above this -> Severe


def _band(value: float, lower_bounds: tuple[float, float, float]) -> Risk:
    moderate, high, severe = lower_bounds
    if value >= severe:
        return Risk.SEVERE
    if value >= high:
        return Risk.HIGH
    if value >= moderate:
        return Risk.MODERATE
    return Risk.LOW


def classify_wind(wind_mph: float, load_lbs: float) -> Risk:
    if wind_mph >= WIND_NO_TRAVEL_MPH:
        return Risk.NO_TRAVEL
    risk = _band(wind_mph, WIND_MPH)
    if risk == Risk.SEVERE and load_lbs > HEAVY_LOAD_NO_TRAVEL_LBS:
        return Risk.NO_TRAVEL
    if risk == Risk.HIGH and load_lbs > HEAVY_LOAD_SEVERE_LBS:
        return Risk.SEVERE
    return risk


def classify_rain(rain_in_hr: float) -> Risk:
    if rain_in_hr > RAIN_NO_TRAVEL_IN_HR:
        return Risk.NO_TRAVEL
    return _band(rain_in_hr, RAIN_IN_HR)


def classify_snow(snow_in_hr: float) -> Risk:
    if snow_in_hr > SNOW_NO_TRAVEL_IN_HR:
        return Risk.NO_TRAVEL
    return _band(snow_in_hr, SNOW_IN_HR)


@dataclass(frozen=True)
class RiskAssessment:
    level: Risk
    wind: Risk
    rain: Risk
    snow: Risk

    @property
    def drivers(self) -> list[str]:
        """Conditions responsible for the overall level (empty when Low)."""
        if self.level == Risk.LOW:
            return []
        return [
            name
            for name, risk in (("wind", self.wind), ("rain", self.rain), ("snow", self.snow))
            if risk == self.level
        ]


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> RiskAssessment:
    """Overall risk is the worst of the three conditions."""
    wind = classify_wind(wind_mph, load_lbs)
    rain = classify_rain(rain_in_hr)
    snow = classify_snow(snow_in_hr)
    return RiskAssessment(level=max(wind, rain, snow), wind=wind, rain=rain, snow=snow)
