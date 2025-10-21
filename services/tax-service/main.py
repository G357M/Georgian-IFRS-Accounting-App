from fastapi import FastAPI
import structlog
from .domain.georgian_tax import GeorgianVATCalculator, VATCalculationRequest, VATCalculationResponse

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Tax Service",
    description="Handles Georgian-specific tax calculations and reporting.",
    version="1.0.0"
)

# In a real app, this might be injected via a dependency container
vat_calculator = GeorgianVATCalculator()

@app.get("/health")
async def health_check():
    """Provides a health check endpoint for the service."""
    logger.info("Health check requested for tax-service")
    return {"status": "healthy", "service": "tax-service"}

@app.post("/api/v1/vat/calculate", response_model=VATCalculationResponse)
async def calculate_vat(request: VATCalculationRequest):
    """
    Calculates Georgian VAT based on the net amount.
    """
    logger.info("VAT calculation requested", net_amount=request.net_amount, is_exempt=request.is_exempt)
    result = vat_calculator.calculate_vat(
        net_amount=request.net_amount,
        is_exempt=request.is_exempt
    )
    return VATCalculationResponse(**result)

# To run this service:
# uvicorn services.tax-service.main:app --host 0.0.0.0 --port 8002 --reload
