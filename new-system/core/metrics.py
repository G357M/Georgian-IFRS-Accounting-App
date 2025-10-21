import time
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge

# --- Business Metrics ---
TRANSACTION_COUNTER = Counter(
    'accounting_transactions_total',
    'Total number of accounting transactions',
    ['status', 'transaction_type', 'currency']
)

TRANSACTION_AMOUNT_HISTOGRAM = Histogram(
    'accounting_transaction_amount_gel',
    'Distribution of transaction amounts in GEL',
    buckets=[10, 50, 100, 500, 1000, 5000, 10000, 50000, float('inf')]
)

ACCOUNT_BALANCE_GAUGE = Gauge(
    'accounting_account_balance_gel',
    'Current account balance in GEL',
    ['account_code', 'account_type']
)

# --- Technical Metrics ---
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status_code']
)

REQUEST_COUNTER = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# --- Middleware for FastAPI ---
async def prometheus_middleware(request: Request, call_next):
    """
    FastAPI middleware to collect Prometheus metrics for each request.
    """
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Get a simplified endpoint path
    endpoint = request.url.path
    # You might want to group dynamic paths, e.g., /users/{id} -> /users
    # for route in request.app.routes:
    #     match, _ = route.matches(request.scope)
    #     if match == Match.FULL:
    #         endpoint = route.path
    #         break

    # Record metrics
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code
    ).observe(duration)
    
    REQUEST_COUNTER.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code
    ).inc()
    
    return response

def add_prometheus_endpoint(app):
    """
    Adds the /metrics endpoint to the FastAPI application.
    """
    from prometheus_client import make_asgi_app

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# --- Example Usage in main.py ---
#
# from .metrics import prometheus_middleware, add_prometheus_endpoint
#
# app = FastAPI(...)
# app.middleware("http")(prometheus_middleware)
# add_prometheus_endpoint(app)
#
# And in your business logic:
#
# TRANSACTION_COUNTER.labels(status='success', transaction_type='sale', currency='GEL').inc()
# TRANSACTION_AMOUNT_HISTOGRAM.observe(amount_in_gel)
# ACCOUNT_BALANCE_GAUGE.labels(account_code='1110', account_type='ASSET').set(15000.75)
