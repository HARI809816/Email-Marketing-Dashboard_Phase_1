from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    ClientCreate, ClientResponse, ApiResponse, ClientAssignRequest, 
    UserRole, ORDER_TYPE_OPTIONS
)
from app.auth import get_current_user, require_manager_or_higher
from app.database import clients_collection, users_collection
from app.services.utils import (
    generate_custom_id, format_mongo_id, resolve_client_handler, 
    resolve_client_handler_bulk, get_user_email_by_name
)
from datetime import datetime
from typing import List

router = APIRouter(tags=["Clients"])

@router.post("/clients", response_model=ApiResponse[ClientResponse])
def create_client(client: ClientCreate, current_user: dict = Depends(get_current_user)):
    # Auto-generate ID if not provided
    if not client.client_id:
        client.client_id = generate_custom_id("CL", clients_collection, current_user)
        
    db_client = clients_collection.find_one({"client_id": client.client_id})
    if db_client:
        raise HTTPException(status_code=400, detail="Client ID already exists")
    
    client_dict = client.model_dump()
    client_dict["created_at"] = datetime.utcnow()
    
    # Associate with employee if created by one
    if current_user["role"] == UserRole.EMPLOYEE:
        client_dict["client_handler"] = current_user["email"]
        
    clients_collection.insert_one(client_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "Client created successfully",
        "data": ClientResponse(**format_mongo_id(client_dict))
    }

@router.get("/clients", response_model=ApiResponse[List[ClientResponse]])
def get_clients(current_user: dict = Depends(get_current_user)):
    query = {}
    if current_user["role"] == UserRole.EMPLOYEE:
        query = {"client_handler": current_user.get("email")}

    # Dynamic aggregation to pull order_type from associated orders
    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "orders",
                "localField": "client_id",
                "foreignField": "client_id",
                "as": "client_orders"
            }
        },
        {
            "$addFields": {
                "order_type": {
                    "$reduce": {
                        "input": {
                            "$setUnion": {
                                "$filter": {
                                    "input": "$client_orders.order_type",
                                    "as": "ot",
                                    "cond": { "$and": [ { "$ne": ["$$ot", None] }, { "$ne": ["$$ot", ""] } ] }
                                }
                            }
                        },
                        "initialValue": "",
                        "in": {
                            "$cond": [
                                { "$eq": ["$$value", ""] },
                                "$$this",
                                { "$concat": ["$$value", ", ", "$$this"] }
                            ]
                        }
                    }
                }
            }
        },
        {"$project": {"client_orders": 0}}
    ]
    
    clients = [format_mongo_id(c) for c in clients_collection.aggregate(pipeline)]
    resolved = resolve_client_handler_bulk(clients)
    
    if current_user["role"] == UserRole.EMPLOYEE:
        employee_names = {current_user.get("full_name")}
        profile_names = set(current_user.get("profile_names", []))
    else:
        employees_data = list(users_collection.find(
            {"role": UserRole.EMPLOYEE}, 
            {"full_name": 1, "profile_names": 1, "_id": 0}
        ))
        employee_names = {emp["full_name"] for emp in employees_data if emp.get("full_name")}
        profile_names = {
            p for emp in employees_data 
            if isinstance(emp.get("profile_names"), list) 
            for p in emp["profile_names"]
        }
                
    detail = {
        "employee_names": list(employee_names),
        "profile_names": list(profile_names),
        "order_type_options": ORDER_TYPE_OPTIONS
    }

    return {
        "status_code": 200,
        "status": "success",
        "message": "Clients fetched successfully",
        "data": [ClientResponse(**c) for c in resolved],
        "detail": detail
    }

@router.get("/clients/{client_id}", response_model=ApiResponse[ClientResponse])
def get_client(client_id: str, current_user: dict = Depends(require_manager_or_higher)):
    client = clients_collection.find_one({"client_id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    return {
        "status_code": 200,
        "status": "success",
        "message": "Client fetched successfully",
        "data": ClientResponse(**format_mongo_id(resolve_client_handler(client)))
    }

@router.post("/clients/assign", response_model=ApiResponse[dict])
def assign_client(request: ClientAssignRequest, current_user: dict = Depends(require_manager_or_higher)):
    client = clients_collection.find_one({"client_id": request.client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    employee_email = get_user_email_by_name(request.employee_email)
    employee = users_collection.find_one({"email": employee_email})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    clients_collection.update_one(
        {"client_id": request.client_id},
        {"$set": {"client_handler": employee_email}}
    )
    
    return {
        "status_code": 200,
        "status": "success",
        "message": f"Client assigned to {employee.get('full_name', employee_email)} successfully"
    }
