"""Place search via Photon (OpenStreetMap data, free, no key, allows autocomplete)."""

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import ProviderError


def _label(props: dict) -> str:
    parts = [props.get("name")]
    for key in ("city", "county", "state"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    if props.get("countrycode") and props["countrycode"] != "US":
        parts.append(props.get("country"))
    return ", ".join(p for p in parts if p)


def search_places(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    key = f"geo:v1:{query.lower()}:{limit}"
    if (hit := cache.get(key)) is not None:
        return hit
    try:
        response = requests.get(
            f"{settings.PHOTON_BASE_URL}/api/",
            params={"q": query, "limit": limit, "lang": "en"},
            headers={"User-Agent": settings.HTTP_USER_AGENT},
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderError("Place search is unavailable right now.") from exc

    try:
        features = response.json().get("features", [])
    except ValueError as exc:
        raise ProviderError("Place search returned an unreadable response.") from exc
    results, seen = [], set()
    for feature in features:
        try:
            lon, lat = feature["geometry"]["coordinates"][:2]
        except (KeyError, TypeError, ValueError):
            continue
        label = _label(feature.get("properties", {}))
        if not label or label in seen:
            continue
        seen.add(label)
        results.append({"label": label, "lat": round(lat, 5), "lon": round(lon, 5)})
    cache.set(key, results, timeout=24 * 3600)
    return results
