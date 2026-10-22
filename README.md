# Weather-Aware Truck Routing

**Live app:** https://weather-aware-truck-routing-henna.vercel.app · **API:** https://truck-routing.31-97-230-124.sslip.io/api/health

A React + Django app that compares three truck routes between two places and recommends the safest one, using the
weather forecast for the time the truck actually reaches each checkpoint, the load weight and the travel time.

- **Frontend:** React 19, TypeScript, Vite, MapLibre GL (OpenFreeMap tiles) and deck.gl
- **Backend:** Django 5.2 + Django REST Framework, pure-Python domain logic, pytest
- **Data:** TomTom truck routing (optional, with a key) or OSRM, Open-Meteo forecasts, Photon geocoding. No paid services are needed.

## What it does

1. You enter an origin, a destination, a departure time, the load weight, and a checkpoint spacing of 10, 25 or 50 miles.
2. The backend gets **3 route options**. When the routing API returns fewer than three distinct routes, it forces extra
   routes through interstate towns off the routes found so far. It rejects candidates that overlap an existing route
   by more than 80%, are more than 1.5× longer or slower, or contain loops and out-and-back spurs.
3. Checkpoints are placed every N miles plus the destination. Each checkpoint's **ETA** is the departure time plus the
   drive time to that point along the route. Weather is the **hourly forecast for that ETA**: wind is the nearest
   hourly sample, and rain and snow are the totals for the hour that contains the ETA.
4. Each checkpoint is classified with the assessment's risk table and load rules (`backend/trips/domain/risk.py`).
5. Routes are ranked, and the winner comes with a one-line reason (for example "Fewest Severe miles: 0 vs 37 mi").
6. The map shows all routes, the selected route coloured by risk, its checkpoints (hover for ETA and conditions), and
   a **corridor heatmap** with a **forecast timeline slider** that runs from departure until the last truck arrives
   (the brief's 0–48 h window, fitted to the trip; trips longer than 48 h extend it, up to 96 h). You can play it
   forward, switch between risk, wind, rain and snow, and watch each route's truck move along at that hour.

## Demo storm mode

When the real weather is calm, everything is Low and the risk logic has nothing to show. Tick **Demo storm** in
the form (or open the app with `?demo=storm`) to add a simulated storm to the real forecast. It is centred on the
fastest route where the alternatives are farthest away, and it peaks when that route's truck arrives there. The core
has about 60 mph wind (No Travel) and 0.8 in/hr rain, fading with distance (an e-folding radius of about 70 mi) and
with time (±12 h), and it drifts east at 20 mph.

The storm only ever makes conditions worse: the stronger wind wins and the rain adds up. The risk rules, load rules,
ranking and heatmap all run unchanged on the combined weather, and the UI labels the result as simulated.
(`backend/trips/domain/demo_storm.py`)

## Risk and recommendation rules, and the choices the brief left open

| | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | <25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

Load rules: 45–54 mph with more than 30,000 lb is No Travel; 35–44 mph with more than 40,000 lb is Severe.

- **Shared band edges** (for example 0.25 in/hr) belong to the higher band. Each band includes its lower bound. The top
  band follows the table: wind ≥55 is No Travel, while rain and snow must be strictly above 1.00 and 3.0.
- **A checkpoint's level** is the worst of wind (after the load rules), rain and snow. The UI shows which condition
  set it.
- **Rain** is liquid precipitation, meaning Open-Meteo's `rain` plus `showers`. **Wind** is the sustained 10 m wind
  speed, as the table specifies. Gusts are shown but don't affect the level.
- **Mile attribution:** each checkpoint covers the road halfway to its neighbours on either side, so every mile is
  counted exactly once.
- **Ranking:** fewest No Travel miles → fewest Severe miles → fewest High miles → lowest mile-weighted average risk
  (Low 0 … No Travel 4) → shortest travel time. The brief's list doesn't mention No Travel; since it is strictly
  worse than Severe, it is ranked first.
- **Forecast range:** departures can be up to 3 days ahead. The weather window (1 past day + 6 forecast days) then
  covers a long drive and its timeline. Any miles beyond the forecast are reported as unknown rather than
  guessed.

## Keeping API usage bounded

Open-Meteo's free tier allows 600 calls a minute and 10,000 a day. We assume each location in a multi-location
request counts as one call, so the backend:

- **Snaps checkpoints to a 0.1° grid** (about 7 mi), so the three routes share weather cells where they overlap.
- **Builds the heatmap** from a corridor grid around the routes, sized to the trip (0.1°–2°).
- **Caps each request** at about 250 checkpoint cells and 220 heatmap cells. Very long trips get a coarser grid
  instead of exceeding the limits; the grid used is reported in the response's `meta` field.
- **Caches per cell and hour**, in a file cache shared by all gunicorn workers. A corridor fetched once is free for
  the next hour, and repeated routes are cached for 6 hours.

A cross-country trip with nothing cached costs at most about 500 locations, and typical trips cost 150–350.

## Run it locally

```bash
# Backend (Python 3.12, uv)
cd backend
uv sync
uv run pytest                  # risk bands, load rules, attribution, ranking, providers, API
uv run python manage.py runserver 127.0.0.1:8000

# Frontend
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api to :8000
```

Optional: put `TOMTOM_API_KEY=...` in `backend/.env` (see `.env.example`) to use TomTom's truck profile, with real
vehicle weight and traffic. Without it, the app uses the public OSRM server's car profile, with every segment capped
at 65 mph to approximate truck speeds.

## API

`POST /api/trips/plan`

```json
{
  "origin": {"lat": 41.8781, "lon": -87.6298, "label": "Chicago"},
  "destination": {"lat": 39.7392, "lon": -104.9903, "label": "Denver"},
  "departure": "2026-10-22T15:00:00Z",
  "load_lbs": 42000,
  "interval_miles": 25
}
```

The response contains the ranked routes (path, checkpoints with ETA, conditions and level, miles per level, average
risk), `recommended_route_id`, `recommendation_reason`, and the heatmap. The heatmap is sent as columnar arrays
(one hourly frame per hour until the last arrival × cells) so the slider never makes another request. `GET /api/geocode?q=` handles place search;
`GET /api/health` is a health check.

## Code map

```
backend/trips/
  domain/risk.py        thresholds + load rules (pure, fully unit tested)
  domain/analysis.py    checkpoints, ETAs, mile attribution, ranking + reason
  domain/geo.py         polyline maths, route similarity, loop/spur detection
  domain/heatmap.py     corridor grid sized to the trip
  providers/            routing (TomTom/OSRM + via-town alternatives), Open-Meteo, Photon
  services.py           orchestration + response shape
frontend/src/
  components/TripMap.tsx         deck.gl layers: heatmap, routes, checkpoints, trucks
  lib/heatmapRaster.ts           corridor grid -> bilinear-filtered image, blended between hourly frames
  components/TimelineControls.tsx trip-length slider, playback, layer picker, legend
  lib/risk.ts                    colours + heatmap ramps aligned to the thresholds
```

## Deployment

- **Frontend:** Vercel, with `frontend` as the project root. `vercel.json` forwards `/api/*` to the backend, so the
  browser only ever talks to one HTTPS origin. Deploy with `deploy/deploy-frontend.sh`.
- **Backend:** a small VPS. gunicorn runs as a systemd service limited to 512 MB of RAM and half a CPU, behind nginx
  with Let's Encrypt. The configs are in `deploy/`, and `deploy/deploy.sh` pulls, syncs and restarts.

## Known limits

- Driver hours-of-service breaks are not added to ETAs.
- The OSRM fallback is a car profile with a speed cap. Truck restrictions (height, weight, hazmat) need the TomTom key.
- Forecasts cover departures up to 3 days ahead.
