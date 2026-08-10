# Observability

This stack keeps metrics and logs in separate stores:

- Prometheus scrapes the API's `/metrics` endpoint.
- Grafana Alloy reads Docker container stdout and forwards it to Loki.
- Grafana provisions both data sources and an API overview dashboard.

## Start

Build and start the API, its local PostgreSQL/Redis dependencies, and the
observability stack together:

```powershell
$env:GRAFANA_ADMIN_PASSWORD = "change-this-password"
docker compose up -d --build
```

Grafana is available at `http://localhost:3000` (user: `admin`). The provisioned
dashboard is **Dashboards > API Observability > API Overview**.

## Verify

1. Send requests to the API, including `/health` and an API endpoint.
2. Open `http://localhost:8000/metrics`.
3. In Grafana Explore, select Loki and query `{container=~".*app.*"}`.
4. In Prometheus, run `http_requests_total`.

The API writes JSON logs to stdout. Do not log request bodies, authorization
headers, passwords, or tokens. Docker captures stdout, and Alloy forwards it to
Loki, so the API does not need a local log file.
