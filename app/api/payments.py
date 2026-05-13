from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    PaymentCreate, PaymentResponse, PaymentHistoryItem, PendingSummaryResponse, 
    PendingClientDetail, ApiResponse
)
from app.auth import get_current_user, require_manager_or_higher
from app.database import payments_collection, payment_history_collection, orders_collection
from app.services.utils import format_mongo_id
from datetime import datetime
from typing import List, Optional

router = APIRouter(tags=["Payments"])

@router.post("/payments", response_model=ApiResponse[PaymentResponse])
def create_payment(payment: PaymentCreate, current_user: dict = Depends(require_manager_or_higher)):
    payment_dict = payment.model_dump()
    payment_dict["created_at"] = datetime.utcnow()
    
    payments_collection.insert_one(payment_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "Payment record created successfully",
        "data": PaymentResponse(**format_mongo_id(payment_dict))
    }

@router.get("/payments", response_model=ApiResponse[List[PaymentResponse]])
def get_payments(current_user: dict = Depends(get_current_user)):
    payments = list(payments_collection.find())
    return {
        "status_code": 200,
        "status": "success",
        "message": "Payments fetched successfully",
        "data": [PaymentResponse(**format_mongo_id(p)) for p in payments]
    }

@router.get("/payments/history", response_model=ApiResponse[List[PaymentHistoryItem]])
def get_payment_history(client_id: Optional[str] = None, order_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if client_id:
        query["client_id"] = client_id
    if order_id:
        query["order_id"] = order_id
        
    history = list(payment_history_collection.find(query).sort("payment_date", -1))
    return {
        "status_code": 200,
        "status": "success",
        "message": "Payment history fetched successfully",
        "data": [PaymentHistoryItem(**format_mongo_id(h)) for h in history]
    }

@router.get("/payments/pending-summary", response_model=ApiResponse[PendingSummaryResponse])
def get_pending_payment_summary(current_user: dict = Depends(require_manager_or_higher)):
    pipeline = [
        {"$group": {
            "_id": "$client_id",
            "total_billed": {"$sum": "$total_amount"},
            "total_paid": {"$sum": "$paid_amount"},
            "orders": {"$push": {
                "order_id": "$order_id",
                "total_amount": "$total_amount",
                "paid_amount": "$paid_amount",
                "balance": {"$subtract": ["$total_amount", "$paid_amount"]}
            }}
        }},
        {"$addFields": {
            "total_balance": {"$subtract": ["$total_billed", "$total_paid"]}
        }},
        {"$match": {"total_balance": {"$gt": 0}}},
        {
            "$lookup": {
                "from": "clients",
                "localField": "_id",
                "foreignField": "client_id",
                "as": "client_info"
            }
        },
        {"$unwind": "$client_info"},
        {"$project": {
            "client_id": "$_id",
            "client_name": "$client_info.name",
            "total_balance": 1,
            "pending_orders": {
                "$filter": {
                    "input": "$orders",
                    "as": "order",
                    "cond": {"$gt": ["$$order.balance", 0]}
                }
            }
        }}
    ]
    
    pending_clients = list(orders_collection.aggregate(pipeline))
    total_pending_amount = sum(c["total_balance"] for c in pending_clients)
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "Pending payments summary fetched successfully",
        "data": {
            "total_pending_amount": total_pending_amount,
            "clients": [PendingClientDetail(**c) for c in pending_clients]
        }
    }
