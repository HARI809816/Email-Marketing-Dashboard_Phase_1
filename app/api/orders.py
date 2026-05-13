from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    ManuscriptCreate, ManuscriptResponse, OrderCreate, OrderResponse, 
    ApiResponse, UserRole
)
from app.auth import get_current_user, require_manager_or_higher
from app.database import manuscripts_collection, orders_collection
from app.services.utils import generate_custom_id, format_mongo_id
from datetime import datetime
from typing import List

router = APIRouter(tags=["Orders"])

@router.post("/manuscripts", response_model=ApiResponse[ManuscriptResponse])
def create_manuscript(manuscript: ManuscriptCreate, current_user: dict = Depends(require_manager_or_higher)):
    db_manuscript = manuscripts_collection.find_one({"manuscript_id": manuscript.manuscript_id})
    if db_manuscript:
        raise HTTPException(status_code=400, detail="Manuscript ID already exists")
    
    manuscript_dict = manuscript.model_dump()
    manuscript_dict["created_at"] = datetime.utcnow()
    
    manuscripts_collection.insert_one(manuscript_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "Manuscript created successfully",
        "data": ManuscriptResponse(**format_mongo_id(manuscript_dict))
    }

@router.get("/manuscripts", response_model=ApiResponse[List[ManuscriptResponse]])
def get_manuscripts(current_user: dict = Depends(get_current_user)):
    manuscripts = list(manuscripts_collection.find())
    return {
        "status_code": 200,
        "status": "success",
        "message": "Manuscripts fetched successfully",
        "data": [ManuscriptResponse(**format_mongo_id(m)) for m in manuscripts]
    }

@router.post("/orders", response_model=ApiResponse[OrderResponse])
def create_order(order: OrderCreate, current_user: dict = Depends(require_manager_or_higher)):
    # Auto-generate Reference ID if not provided
    if not order.reference_id:
        order.reference_id = generate_custom_id("REF", orders_collection, current_user)
        
    db_order = orders_collection.find_one({"order_id": order.order_id})
    if db_order:
        raise HTTPException(status_code=400, detail="Order ID already exists")
    
    order_dict = order.model_dump()
    order_dict["created_at"] = datetime.utcnow()
    
    orders_collection.insert_one(order_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "Order created successfully",
        "data": OrderResponse(**format_mongo_id(order_dict))
    }

@router.get("/orders", response_model=ApiResponse[List[OrderResponse]])
def get_orders(current_user: dict = Depends(get_current_user)):
    query = {}
    # Employees can only see their own orders if linked via client? 
    # Logic depends on your specific business rules.
    orders = list(orders_collection.find(query))
    return {
        "status_code": 200,
        "status": "success",
        "message": "Orders fetched successfully",
        "data": [OrderResponse(**format_mongo_id(o)) for o in orders]
    }
