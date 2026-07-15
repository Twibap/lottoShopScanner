# Backend API

PostGIS-backed read API for nearby lotto shops.

## Run locally

```powershell
docker compose up --build postgres backend
```

If the PostgreSQL volume was created before PostGIS support was added, apply the
idempotent schema once before starting the backend:

```powershell
docker compose exec -T postgres psql -U lotto -d lotto `
  -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/001-init.sql
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

```text
GET /v1/shops/nearby?lat=37.5665&lng=126.9780&radius_m=3000&sort=distance&limit=30
```

Supported sort values are `distance`, `first_wins`, `second_wins`, `total_prize`,
and `recent_win`. Radius is limited to 0–10,000 metres and page size to 1–100.
Only physical shops with coordinates inside the accepted South Korea bounds are indexed.

Place search is available at:

```text
GET /v1/places/search?q=서울%20중구&limit=10
```

If `NAVER_GEOCODE_CLIENT_ID` and `NAVER_GEOCODE_CLIENT_SECRET` are set, NAVER
address geocoding results are returned before shop database matches. Without
those variables, search falls back to shop name, address, and region matches.

Shop detail is available at:

```text
GET /v1/shops/11100928?lat=37.5665&lng=126.9780&radius_m=3000&sort=distance
```

The optional coordinate context returns distance and the shop's current rank
inside the selected radius and sort mode. The detail response also includes
national helper ranks and individual first/second prize winning history.

## Test

```powershell
python -m unittest discover -s apps/backend/tests -v
```
