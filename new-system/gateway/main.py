import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Georgian Accounting API Gateway",
    description="Central API gateway for all accounting microservices.",
    version="1.0.0"
)

# Service registry: In a real-world scenario, this would be dynamic (e.g., from Consul or Kubernetes services)
SERVICE_REGISTRY = {
    "accounting": "http://localhost:8001", # Should be the service name in Docker/K8s
    "tax": "http://localhost:8002",
    # "payroll": "http://payroll-service:8003",
    # "reporting": "http://reporting-service:8004"
}

@app.api_route("/api/v1/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(service_name: str, path: str, request: Request):
    """
    Proxies incoming requests to the appropriate downstream microservice.
    """
    if service_name not in SERVICE_REGISTRY:
        logger.warning("Service not found in registry", service_name=service_name)
        raise HTTPException(status_code=404, detail="Service not found")
    
    service_url = SERVICE_REGISTRY[service_name]
    target_url = f"{service_url}/{path}"
    
    logger.info("Proxying request",
                method=request.method,
                target_url=target_url,
                client_host=request.client.host)

    # In a real gateway, you would handle authentication, rate limiting, etc. here.
    # For example, decode a JWT and add user info to the headers.
    headers = dict(request.headers)
    headers["X-Forwarded-For"] = request.client.host
    # headers["X-User-ID"] = "user-from-jwt" # Example

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                content=await request.body(),
                headers=headers,
                params=request.query_params,
                timeout=30.0
            )
            
            # To avoid issues with certain headers, create a clean response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except httpx.ConnectError as e:
            logger.error("Failed to connect to downstream service", service=service_name, error=str(e))
            return JSONResponse(
                status_code=503,
                content={"detail": f"Service '{service_name}' is unavailable."}
            )
        except Exception as e:
            logger.error("An unexpected error occurred in the gateway", error=str(e), exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "An internal gateway error occurred."}
            )

# To run the gateway:
# uvicorn new-system.gateway.main:app --host 0.0.0.0 --port 8000 --reload