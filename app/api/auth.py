from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import LoginRequest, LoginResponse, OTPVerifyRequest, ApiResponse
from app.auth import create_access_token, verify_password
from app.database import users_collection, tokens_collection, otps_collection
from app.services.email import send_otp_email
import random
from datetime import datetime, timedelta

router = APIRouter(tags=["Authentication"])

@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(request: LoginRequest):
    user = users_collection.find_one({"email": request.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate OTP
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP
    otps_collection.update_one(
        {"email": request.email},
        {"$set": {"otp": otp, "expires_at": expires_at}},
        upsert=True
    )
    
    # Send OTP via email
    await send_otp_email(request.email, otp)
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "OTP sent to your email",
        "data": LoginResponse(email=request.email)
    }

@router.post("/verify-otp", response_model=ApiResponse[dict])
def verify_otp(request: OTPVerifyRequest):
    otp_record = otps_collection.find_one({"email": request.email})
    
    if not otp_record or otp_record["otp"] != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if datetime.utcnow() > otp_record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # Success - clear OTP
    otps_collection.delete_one({"email": request.email})
    
    user = users_collection.find_one({"email": request.email})
    access_token = create_access_token(data={"sub": user["email"]})
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "OTP verified successfully",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"]
            }
        }
    }
