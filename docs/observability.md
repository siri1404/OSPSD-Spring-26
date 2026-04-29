# Observability & Monitoring

This document explains the telemetry and monitoring setup for the Cloud Storage Service using Prometheus and Grafana.

## Overview

The service exposes Prometheus metrics at the `/metrics` endpoint, which are scraped by a Prometheus server and visualized in Grafana dashboards.

## Architecture

```
Cloud Storage Service (FastAPI)
    ↓ exposes /metrics
Prometheus (scrapes every 10s)
    ↓ stores time-series data
Grafana (visualizes metrics)
```

## Metrics Exposed

### 1. **requests_total** (Counter)
Total number of HTTP requests received.

**Labels:**
- `endpoint` - Request path (e.g., `/upload`, `/list`)
- `method` - HTTP method (GET, POST, DELETE, etc.)
- `status_code` - HTTP status code (200, 404, 500, etc.)

**Example PromQL:**
```promql
# Total requests per second
rate(requests_total[5m])

# Requests by endpoint
sum(rate(requests_total[5m])) by (endpoint)

# Success rate (2xx responses)
100 * (sum(rate(requests_total{status_code=~"2.."}[5m])) / sum(rate(requests_total[5m])))
```

---

### 2. **request_latency_seconds** (Histogram)
HTTP request latency in seconds.

**Labels:**
- `endpoint` - Request path
- `method` - HTTP method

**Buckets:** 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0 seconds

**Example PromQL:**
```promql
# p50 latency
histogram_quantile(0.50, sum(rate(request_latency_seconds_bucket[5m])) by (le, endpoint))

# p95 latency
histogram_quantile(0.95, sum(rate(request_latency_seconds_bucket[5m])) by (le, endpoint))

# p99 latency
histogram_quantile(0.99, sum(rate(request_latency_seconds_bucket[5m])) by (le, endpoint))
```

---

### 3. **errors_total** (Counter)
Total number of HTTP errors.

**Labels:**
- `endpoint` - Request path
- `error_type` - Error category (`4xx` for client errors, `5xx` for server errors)

**Example PromQL:**
```promql
# Error rate per second
rate(errors_total[5m])

# 4xx vs 5xx errors
sum(rate(errors_total{error_type="4xx"}[5m]))
sum(rate(errors_total{error_type="5xx"}[5m]))
```

---

### 4. **ai_tool_calls_total** (Counter)
Total number of AI tool calls made by the Gemini client.

**Labels:**
- `tool_name` - Name of the storage tool called (e.g., `list_files`, `upload_file`, `delete_file`)
- `status` - Call result (`success` or `failure`)

**Example PromQL:**
```promql
# AI tool call rate
rate(ai_tool_calls_total[5m])

# Success rate by tool
100 * (sum(rate(ai_tool_calls_total{status="success"}[5m])) by (tool_name) / sum(rate(ai_tool_calls_total[5m])) by (tool_name))

# Failed tool calls
sum(rate(ai_tool_calls_total{status="failure"}[5m])) by (tool_name)
```

---

## Grafana Dashboard

The pre-configured Grafana dashboard includes the following panels:

### Panel 1: Request Latency (p50, p95, p99)
- **Type:** Time series graph
- **Metrics:** Latency percentiles by endpoint
- **Use case:** Monitor response times and identify slow endpoints

### Panel 2: Total Requests Over Time
- **Type:** Time series graph (stacked)
- **Metrics:** Request rate by endpoint and method
- **Use case:** Track traffic patterns and usage trends

### Panel 3: Error Rate (4xx vs 5xx)
- **Type:** Time series graph (stacked)
- **Metrics:** Error rates split by type
- **Use case:** Monitor system health and identify issues

### Panel 4: AI Tool Call Success/Failure Rates
- **Type:** Time series graph (stacked)
- **Metrics:** AI tool invocation rates by status
- **Use case:** Track AI integration reliability

### Panel 5: Overall Success Rate (2xx)
- **Type:** Gauge
- **Metrics:** Percentage of successful requests
- **Use case:** Quick health check indicator

### Panel 6: AI Tool Success Rate
- **Type:** Gauge
- **Metrics:** Percentage of successful AI tool calls
- **Use case:** AI integration health indicator

### Panel 7: Requests by Endpoint
- **Type:** Pie chart
- **Metrics:** Request distribution by endpoint
- **Use case:** Understand endpoint usage patterns

---

## Running Locally

### Prerequisites
- Docker and Docker Compose installed
- Service running on `http://localhost:8000`

### Option 1: Using Docker Compose (Recommended)

Create a `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  prometheus:
    build:
      context: ./monitoring
      dockerfile: Dockerfile.prometheus
    ports:
      - "9090:9090"
    volumes:
      - prometheus-data:/prometheus
    networks:
      - monitoring

  grafana:
    build:
      context: ./monitoring
      dockerfile: Dockerfile.grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_SERVER_HTTP_PORT=3000
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - monitoring
    depends_on:
      - prometheus

volumes:
  prometheus-data:
  grafana-data:

networks:
  monitoring:
```

**Run:**
```bash
docker-compose up -d
```

**Access:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

### Option 2: Manual Setup

**Run Prometheus:**
```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus:latest
```

**Run Grafana:**
```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_USER=admin \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  -v $(pwd)/monitoring/grafana_dashboard.json:/var/lib/grafana/dashboards/cloud-storage.json \
  grafana/grafana:latest
```

---

## Production Deployment (Render)

### Services Deployed

1. **Cloud Storage Service** (FastAPI)
   - Exposes `/metrics` endpoint
   - URL: https://cloud-storage-service-mcni.onrender.com

2. **Prometheus** (Private Service)
   - Scrapes metrics from cloud storage service
   - Internal port: 9090

3. **Grafana** (Web Service)
   - Visualizes metrics from Prometheus
   - URL: Set by Terraform output `grafana_url`

### Environment Variables

**Grafana:**
- `GF_SECURITY_ADMIN_USER` - Admin username (default: `admin`)
- `GF_SECURITY_ADMIN_PASSWORD` - Admin password (set in Render dashboard)
- `GF_SERVER_HTTP_PORT` - HTTP port (default: `3000`)

**Prometheus:**
- `PROMETHEUS_SCRAPE_TARGET` - Target to scrape (set to `cloud-storage-service-mcni.onrender.com`)

### Accessing Production Dashboards

1. Get Grafana URL from Terraform output:
   ```bash
   cd infrastructure
   terraform output grafana_url
   ```

2. Login with admin credentials (set in Render dashboard)

3. Navigate to **"Cloud Storage Service Metrics"** dashboard

---

## Testing Metrics

### 1. Check Metrics Endpoint
```bash
curl http://localhost:8000/metrics
```

Expected output:
```
# HELP requests_total Total number of HTTP requests
# TYPE requests_total counter
requests_total{endpoint="/health",method="GET",status_code="200"} 42.0

# HELP request_latency_seconds HTTP request latency in seconds
# TYPE request_latency_seconds histogram
request_latency_seconds_bucket{endpoint="/upload",method="POST",le="0.005"} 10.0
...
```

### 2. Generate Test Traffic
```bash
# Health check
curl http://localhost:8000/health

# Upload file
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"

# List files
curl http://localhost:8000/list \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Verify in Prometheus
1. Open http://localhost:9090
2. Query: `rate(requests_total[1m])`
3. Graph should show recent requests

### 4. Verify in Grafana
1. Open http://localhost:3000
2. Navigate to dashboard
3. Check panels update with new data

---

## Troubleshooting

### Metrics Not Appearing

**Issue:** `/metrics` returns 404

**Solution:**
1. Verify prometheus-client is installed:
   ```bash
   uv sync
   ```
2. Check middleware is added to FastAPI app:
   ```python
   app.add_middleware(PrometheusMiddleware)
   ```

---

**Issue:** Prometheus shows "target down"

**Solution:**
1. Check service is running: `curl http://localhost:8000/health`
2. Verify scrape target in `prometheus.yml` matches service URL
3. Check network connectivity

---

**Issue:** Grafana shows "No data"

**Solution:**
1. Verify Prometheus datasource is configured correctly
2. Check Prometheus is scraping: http://localhost:9090/targets
3. Verify queries in dashboard panels match metric names

---

## Metric Retention

- **Prometheus:** Default 15 days (configurable via `--storage.tsdb.retention.time`)
- **Grafana:** No data storage (queries Prometheus in real-time)

---

## Performance Impact

The telemetry middleware adds minimal overhead:
- **Latency:** ~0.1-0.5ms per request
- **Memory:** ~10-50MB for metric storage (per service instance)
- **CPU:** Negligible (<1% for typical traffic)

---

## Best Practices

1. **Alert on high error rates** (>5% 5xx errors)
2. **Monitor p95/p99 latency** (set SLOs based on requirements)
3. **Track AI tool success rate** (should be >95%)
4. **Set up retention policies** in Prometheus for long-term storage
5. **Use dashboards for incident response** and performance analysis

---

## Further Reading

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Histogram vs Summary](https://prometheus.io/docs/practices/histograms/)
