from decimal import Decimal, getcontext
from pydantic import BaseModel, Field
from typing import Dict

# Set precision for decimal calculations
getcontext().prec = 15

class GeorgianVATCalculator:
    """
    Handles VAT calculations according to Georgian tax law.
    """
    STANDARD_RATE = Decimal('0.18')  # 18% VAT rate
    REGISTRATION_THRESHOLD = Decimal('100000.00')  # 100,000 GEL annual turnover

    def calculate_vat(self, net_amount: Decimal, is_exempt: bool = False) -> Dict[str, Decimal]:
        """
        Calculates VAT for a given net amount.
        """
        if is_exempt:
            return {
                "net_amount": net_amount,
                "vat_amount": Decimal('0.00'),
                "gross_amount": net_amount,
                "vat_rate": Decimal('0.00')
            }
        
        vat_amount = (net_amount * self.STANDARD_RATE).quantize(Decimal('0.01'))
        gross_amount = net_amount + vat_amount
        
        return {
            "net_amount": net_amount,
            "vat_amount": vat_amount,
            "gross_amount": gross_amount,
            "vat_rate": self.STANDARD_RATE
        }

    def check_vat_registration_requirement(self, annual_turnover: Decimal) -> bool:
        """
        Checks if a company is required to register as a VAT payer.
        """
        return annual_turnover >= self.REGISTRATION_THRESHOLD

# --- Pydantic models for API ---
class VATCalculationRequest(BaseModel):
    net_amount: Decimal = Field(..., gt=0, description="The net amount before VAT.")
    is_exempt: bool = Field(False, description="Whether the transaction is exempt from VAT.")

class VATCalculationResponse(BaseModel):
    net_amount: Decimal
    vat_amount: Decimal
    gross_amount: Decimal
    vat_rate: Decimal
