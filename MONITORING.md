# Monitoring & Observability Setup

Comprehensive monitoring and observability system for the Agent Dashboard with structured JSON logging, performance metrics, health checks, and Prometheus integration.

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Structured Logging](#structured-logging)
5. [Performance Metrics](#performance-metrics)
6. [Health Endpoints](#health-endpoints)
7. [Prometheus Integration](#prometheus-integration)
8. [Monitoring Dashboard](#monitoring-dashboard)
9. [Alerts & Notifications](#alerts--notifications)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)

## Overview

The monitoring and observability system provides comprehensive insights into the Agent Dashboard's health, performance, and behavior. It includes:

- **Structured JSON Logging**: Machine-readable logs for easy aggregation and analysis
- **Performance Metrics**: Request timing, resource usage, and custom business metrics
- **Health Checks**: Detailed system status with CPU, memory, disk, and service metrics
- **Prometheus Integration**: Industry-standard metrics export for monitoring systems
- **Visual Dashboard**: Real-time monitoring dashboard with auto-refresh
- **Alerting**: Automatic detection of resource threshold breaches

## Features

### 1. Structured JSON Logging

- JSON-formatted logs for easy parsing and aggregation
- Structured context fields (user_id, request_id, correlation_id, etc.)
- Exception tracking with stack traces
- Performance metrics logging
- Multiple log outputs (console, file, rotating logs)

### 2. Performance Metrics Collection

- **Counters**: Monotonically increasing values (requests, errors, etc.)
- **Gauges**: Point-in-time values (active connections, memory usage, etc.)
- **Histograms**: Distribution tracking (response times, request sizes, etc.)
- **Labels**: Multi-dimensional metrics with tags
- **Export Formats**: JSON and Prometheus text format

### 3. Enhanced Health Endpoints

- `/health` - Comprehensive health check with system metrics
- `/api/system/status` - Detailed system status with alerts
- `/metrics` - Prometheus-formatted metrics export
- `/monitoring` - Visual monitoring dashboard

### 4. Real-Time Monitoring

- WebSocket support for live metrics streaming
- Auto-refreshing dashboard (5-second intervals)
- Visual indicators for healthy/degraded/unhealthy states
- Resource usage graphs and progress bars

## Quick Start

### Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- `psutil>=5.9.0` - System metrics
- `aiohttp>=3.9.0` - HTTP server
- `pytest>=7.0.0` - Testing
- `pytest-asyncio>=0.21.0` - Async testing
- `playwright>=1.40.0` - Browser testing

### Basic Setup

```python
from dashboard.server import DashboardServer
from dashboard.logging_config import setup_logging

# Setup structured logging
setup_logging(
    log_level="INFO",
    enable_json=True,
    enable_color=True
)

# Create dashboard server with monitoring
server = DashboardServer(
    project_name="my-project",
    port=8080,
    host="127.0.0.1"
)

# Run server
server.run()
```

### Access Monitoring

- Health Check: http://localhost:8080/health
- Prometheus Metrics: http://localhost:8080/metrics
- Monitoring Dashboard: http://localhost:8080/monitoring
- System Status: http://localhost:8080/api/system/status

## Structured Logging

### Configuration

```python
from dashboard.logging_config import setup_logging, get_logger

# Setup logging with custom configuration
setup_logging(
    log_level="DEBUG",              # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_dir=Path("./logs"),         # Directory for log files
    log_file="app.log",             # Main log file
    error_log_file="errors.log",    # Error-only log file
    enable_console=True,            # Console output
    enable_json=True,               # JSON format for files
    enable_color=True               # Colored console output
)

# Get logger for your module
logger = get_logger(__name__)
```

### Usage Examples

```python
# Basic logging
logger.info("User logged in")
logger.warning("Rate limit approaching")
logger.error("Database connection failed")

# Logging with structured context
logger.info("API request completed", extra={
    "user_id": "123",
    "endpoint": "/api/metrics",
    "duration_ms": 150,
    "status_code": 200
})

# Exception logging
try:
    risky_operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True, extra={
        "operation": "risky_operation",
        "user_id": user_id
    })

# Performance metric logging
from dashboard.logging_config import log_performance_metric

log_performance_metric(
    logger,
    "database_query",
    duration_ms=25.5,
    query_type="SELECT",
    table="users"
)
```

### Log Format

JSON logs include:

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "dashboard.server",
  "message": "API request completed",
  "module": "server",
  "function": "get_metrics",
  "line": 291,
  "process_id": 12345,
  "thread_id": 67890,
  "thread_name": "MainThread",
  "extra": {
    "user_id": "123",
    "endpoint": "/api/metrics",
    "duration_ms": 150,
    "status_code": 200
  }
}
```

## Performance Metrics

### Configuration

```python
from dashboard.performance_metrics import (
    metrics_collector,
    increment_counter,
    set_gauge,
    record_metric,
    track_time,
    timed_operation,
    register_metric
)

# Register metric metadata (for Prometheus export)
register_metric(
    "http_requests_total",
    "counter",
    "Total HTTP requests",
    unit="requests"
)
```

### Usage Examples

#### Counters

```python
# Increment counter
increment_counter("http_requests_total", 1, {"endpoint": "/api/metrics"})
increment_counter("login_attempts", 1, {"status": "success"})

# Get counter value
value = metrics_collector.get_counter("http_requests_total", {"endpoint": "/api/metrics"})
```

#### Gauges

```python
# Set gauge value
set_gauge("active_connections", 25)
set_gauge("queue_size", 100, {"queue": "processing"})

# Get gauge value
value = metrics_collector.get_gauge("active_connections")
```

#### Histograms

```python
# Record observation
record_metric("request_duration", 0.150)  # 150ms
record_metric("response_size", 1024, {"endpoint": "/api/metrics"})

# Get histogram data
hist = metrics_collector.get_histogram("request_duration")
print(f"Mean: {hist.mean}, P95: {hist.percentile(95)}")
```

#### Decorators

```python
# Track function execution time
@track_time("process_data_duration")
def process_data(data):
    # Processing logic
    return result

# Context manager for timing
with timed_operation("database_query", {"query": "SELECT"}):
    results = db.execute(query)
```

### Exporting Metrics

```python
# Export as JSON
metrics = metrics_collector.get_metrics()
print(json.dumps(metrics, indent=2))

# Export as Prometheus format
prom_text = metrics_collector.export_prometheus()
print(prom_text)
```

## Health Endpoints

### /health - Basic Health Check

Returns comprehensive health information including:
- Service status (healthy/unhealthy)
- System metrics (CPU, memory, disk)
- Metrics store status
- Performance summary
- Uptime

Example response:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "project": "agent-dashboard",
  "service": {
    "name": "agent-dashboard",
    "uptime_seconds": 3600,
    "host": "127.0.0.1",
    "port": 8080,
    "websocket_connections": 2
  },
  "system": {
    "cpu_percent": 15.5,
    "memory_percent": 45.2,
    "memory_used_mb": 512,
    "memory_total_mb": 8192,
    "disk_percent": 65.0,
    "disk_used_gb": 250,
    "disk_total_gb": 500
  },
  "metrics_store": {
    "metrics_file_exists": true,
    "event_count": 1500,
    "session_count": 25,
    "agent_count": 14
  }
}
```

### /api/system/status - Detailed System Status

Returns detailed system information including:
- System metrics (CPU, memory, disk, network)
- Process information
- Active alerts
- Performance metrics

Includes automatic alerting for:
- CPU > 80%
- Memory > 85%
- Disk > 90%

### /metrics - Prometheus Metrics

Exports metrics in Prometheus text format for scraping:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/api/metrics"} 1250

# HELP request_duration_seconds Request duration
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.1"} 800
request_duration_seconds_bucket{le="0.5"} 1200
request_duration_seconds_bucket{le="+Inf"} 1250
request_duration_seconds_sum 150.5
request_duration_seconds_count 1250

# HELP active_connections Current active connections
# TYPE active_connections gauge
active_connections 25
```

## Prometheus Integration

### Setup Prometheus Scraping

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'agent-dashboard'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
```

### Useful Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# Average response time
rate(request_duration_seconds_sum[5m]) / rate(request_duration_seconds_count[5m])

# 95th percentile response time
histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status="error"}[5m]) / rate(http_requests_total[5m])
```

### Grafana Dashboard

Import the provided Grafana dashboard JSON (see `grafana_dashboard.json`) for visualization.

Key panels:
- Request Rate
- Response Time (P50, P95, P99)
- Error Rate
- CPU / Memory / Disk Usage
- Active Connections

## Monitoring Dashboard

### Accessing the Dashboard

Navigate to: http://localhost:8080/monitoring

### Features

- **Real-time Updates**: Auto-refreshes every 5 seconds
- **Health Overview**: Service health, CPU, memory, disk usage
- **Metrics Store**: Event count, session count, agent count
- **Performance**: Request count, average response time
- **Alerts**: Active alerts with severity indicators
- **Network Statistics**: Bytes sent/received, packet counts
- **Process Information**: PID, memory usage, thread count

### Visual Indicators

- **Green**: Healthy (< 70% resource usage)
- **Yellow**: Warning (70-85% resource usage)
- **Red**: Critical (> 85% resource usage)

## Alerts & Notifications

### Automatic Alerting

The system automatically generates alerts for:

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| CPU Usage | 70% | 85% |
| Memory Usage | 75% | 85% |
| Disk Usage | 80% | 90% |

### Alert Format

```json
{
  "severity": "warning",
  "message": "High CPU usage: 75.5%",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Custom Alerts

Add custom alerting logic in `server.py`:

```python
# Check custom condition
if custom_metric > threshold:
    alerts.append({
        "severity": "warning",
        "message": f"Custom metric exceeded: {custom_metric}",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
```

## Testing

### Running Tests

```bash
# Run all monitoring tests
pytest tests/test_monitoring.py -v

# Run specific test class
pytest tests/test_monitoring.py::TestStructuredLogging -v

# Run with coverage
pytest tests/test_monitoring.py --cov=dashboard --cov-report=html

# Run browser tests (requires Playwright)
pytest tests/test_monitoring_playwright.py -v
```

### Test Coverage

The test suite includes:

1. **Structured Logging Tests** (5 tests)
   - JSON formatter validation
   - Extra fields handling
   - Exception logging

2. **Performance Metrics Tests** (9 tests)
   - Counter operations
   - Gauge operations
   - Histogram operations
   - Labels and tags
   - Decorators and context managers
   - Prometheus export

3. **Health Endpoint Tests** (9 tests)
   - Detailed health information
   - System metrics
   - Service information
   - Prometheus format
   - Concurrent requests

4. **Integration Tests** (2 tests)
   - End-to-end workflows
   - Combined functionality

5. **Browser Tests** (12 tests)
   - Dashboard rendering
   - Visual elements
   - Auto-refresh
   - Responsive design
   - Screenshots

### Browser Testing

```bash
# Install Playwright browsers
playwright install chromium

# Run browser tests
pytest tests/test_monitoring_playwright.py -v -s

# Screenshots are saved to: test_screenshots/
```

## Troubleshooting

### Common Issues

#### Issue: Logs not appearing in file

**Solution**: Check log directory permissions and disk space

```bash
# Check permissions
ls -la logs/

# Create log directory
mkdir -p logs
chmod 755 logs
```

#### Issue: Metrics not being collected

**Solution**: Ensure metrics collector is initialized

```python
from dashboard.performance_metrics import metrics_collector

# Reset collector if needed
metrics_collector.reset()

# Verify metrics
metrics = metrics_collector.get_metrics()
print(metrics)
```

#### Issue: Health endpoint returns 503

**Solution**: Check system resource availability

```bash
# Check system resources
python3 -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%')"
```

#### Issue: Prometheus scraping fails

**Solution**: Verify endpoint is accessible

```bash
# Test endpoint
curl http://localhost:8080/metrics

# Check Prometheus logs
docker logs prometheus
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
setup_logging(log_level="DEBUG")
```

Or set environment variable:

```bash
export LOG_LEVEL=DEBUG
python dashboard/server.py
```

### Performance Optimization

For high-traffic deployments:

1. **Reduce broadcast interval**:
   ```python
   server.broadcast_interval = 10  # Increase to 10 seconds
   ```

2. **Limit metric history**:
   ```python
   metrics_collector.MAX_EVENTS = 100  # Reduce from 500
   ```

3. **Use external logging aggregation**:
   - Configure log forwarding to ELK stack, Splunk, or CloudWatch
   - Disable local file logging in production

## Best Practices

1. **Logging**:
   - Use appropriate log levels (DEBUG for development, INFO for production)
   - Include context fields for better filtering
   - Avoid logging sensitive information (passwords, tokens)

2. **Metrics**:
   - Use labels sparingly (high cardinality can impact performance)
   - Register metric metadata for better Prometheus documentation
   - Set up retention policies for historical data

3. **Monitoring**:
   - Set up alerting on critical metrics
   - Monitor dashboard performance regularly
   - Review logs for anomalies

4. **Security**:
   - Bind to localhost (127.0.0.1) for development
   - Use reverse proxy (nginx/caddy) for production
   - Enable authentication on monitoring endpoints

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Dashboard Guide](https://grafana.com/docs/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [psutil Documentation](https://psutil.readthedocs.io/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review test cases for usage examples
3. Open an issue on GitHub with logs and reproduction steps

---

**Version**: 1.0.0
**Last Updated**: 2024-01-01
**License**: MIT
