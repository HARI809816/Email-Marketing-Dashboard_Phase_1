from fastapi import APIRouter, HTTPException
from app.currency_converter import convert_inr_to_usd, convert_usd_to_inr, get_current_rate_info
from app.schemas import ApiResponse

router = APIRouter(tags=["Tools"])

@router.get("/exchange-rate", response_model=ApiResponse[dict])
def get_exchange_rate():
    rate_info = get_current_rate_info()
    if not rate_info:
        raise HTTPException(status_code=503, detail="Exchange rate service unavailable")
    return {
        "status_code": 200,
        "status": "success",
        "message": "Exchange rate fetched successfully",
        "data": rate_info
    }

@router.post("/convert/inr-to-usd", response_model=ApiResponse[dict])
def convert_inr_to_usd_endpoint(amount: dict):
    amount_inr = amount.get("amount_inr")
    if amount_inr is None or amount_inr < 0:
        raise HTTPException(status_code=400, detail="Invalid amount_inr")
    
    result = convert_inr_to_usd(float(amount_inr))
    if not result:
        raise HTTPException(status_code=503, detail="Exchange rate service unavailable")
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "Conversion completed successfully",
        "data": result
    }

@router.post("/convert/usd-to-inr", response_model=ApiResponse[dict])
def convert_usd_to_inr_endpoint(amount: dict):
    amount_usd = amount.get("amount_usd")
    if amount_usd is None or amount_usd < 0:
        raise HTTPException(status_code=400, detail="Invalid amount_usd")
    
    result = convert_usd_to_inr(float(amount_usd))
    if not result:
        raise HTTPException(status_code=503, detail="Exchange rate service unavailable")
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "Conversion completed successfully",
        "data": result
    }
