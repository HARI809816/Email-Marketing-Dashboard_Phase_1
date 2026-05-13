from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    UserCreate, UserResponse, UserDetailResponse, ApiResponse, 
    PasswordUpdate, AdminPasswordUpdate, PermissionUpdate, ProfileUpdate, UserRole
)
from app.auth import get_current_user, require_admin, require_manager_or_higher, encrypt_password
from app.database import users_collection
from app.services.utils import is_id_range_overlapping, format_mongo_id
from datetime import datetime
from typing import List

router = APIRouter(tags=["Users"])

@router.post("/init-super-admin", response_model=ApiResponse[dict], status_code=status.HTTP_201_CREATED)
def init_super_admin(user: UserCreate):
    admin_count = users_collection.count_documents({"role": UserRole.ADMIN})
    if admin_count >= 5:
        raise HTTPException(status_code=400, detail="Initialization limit reached")
    
    db_user = users_collection.find_one({"email": user.email})
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user.model_dump()
    user_dict["password"] = encrypt_password(user_dict["password"])
    user_dict["role"] = UserRole.ADMIN
    user_dict["created_at"] = datetime.utcnow()
    
    users_collection.insert_one(user_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "Super Admin initialized successfully",
        "data": {"email": user.email}
    }

@router.post("/create-user", response_model=ApiResponse[UserResponse])
def create_user(user: UserCreate, current_user: dict = Depends(require_manager_or_higher)):
    db_user = users_collection.find_one({"email": user.email})
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check for ID range overlap
    if user.id_range_start is not None and user.id_range_end is not None:
        overlapping_user = is_id_range_overlapping(user.id_range_start, user.id_range_end)
        if overlapping_user:
            raise HTTPException(
                status_code=400, 
                detail=f"ID range {user.id_range_start}-{user.id_range_end} overlaps with user: {overlapping_user}"
            )
    
    # Logic for Admin role restriction
    if user.role == UserRole.ADMIN:
        if current_user["role"] != UserRole.ADMIN:
             raise HTTPException(status_code=403, detail="Only Admins can create other Admins")

    user_dict = user.model_dump()
    user_dict["password"] = encrypt_password(user_dict["password"])
    user_dict["created_at"] = datetime.utcnow()
    
    users_collection.insert_one(user_dict)
    return {
        "status_code": 201,
        "status": "success",
        "message": "User created successfully",
        "data": UserResponse(**user_dict)
    }

@router.get("/users/all", response_model=ApiResponse[List[UserResponse]])
def get_all_users(current_user: dict = Depends(require_manager_or_higher)):
    users = list(users_collection.find({"role": {"$ne": UserRole.ADMIN}}))
    return {
        "status_code": 200,
        "status": "success",
        "message": "Users fetched successfully",
        "data": [UserResponse(**format_mongo_id(u)) for u in users]
    }

@router.get("/users/admins", response_model=ApiResponse[List[UserResponse]])
def get_all_admins(current_user: dict = Depends(require_admin)):
    admins = list(users_collection.find({"role": UserRole.ADMIN}))
    return {
        "status_code": 200,
        "status": "success",
        "message": "Admins fetched successfully",
        "data": [UserResponse(**format_mongo_id(u)) for u in admins]
    }

@router.patch("/users/permissions", response_model=ApiResponse[dict])
def update_user_permissions(data: PermissionUpdate, current_user: dict = Depends(require_manager_or_higher)):
    target_user = users_collection.find_one({"email": data.email})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_user["role"] == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin permissions cannot be modified")

    # Check for ID range overlap
    if data.id_range_start is not None and data.id_range_end is not None:
        overlapping_user = is_id_range_overlapping(data.id_range_start, data.id_range_end, exclude_email=data.email)
        if overlapping_user:
            raise HTTPException(
                status_code=400, 
                detail=f"ID range {data.id_range_start}-{data.id_range_end} overlaps with user: {overlapping_user}"
            )

    users_collection.update_one(
        {"email": data.email},
        {"$set": {
            "permissions": data.permissions,
            "branch": data.branch,
            "id_range_start": data.id_range_start,
            "id_range_end": data.id_range_end
        }}
    )
    
    return {
        "status_code": 200,
        "status": "success",
        "message": "Permissions updated successfully"
    }

@router.get("/users/me", response_model=ApiResponse[UserResponse])
def get_own_details(current_user: dict = Depends(get_current_user)):
    return {
        "status_code": 200,
        "status": "success",
        "message": "Details fetched successfully",
        "data": UserResponse(**format_mongo_id(current_user))
    }

@router.get("/users/{email}/details", response_model=ApiResponse[UserDetailResponse])
def get_user_details(email: str, current_user: dict = Depends(require_manager_or_higher)):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "status_code": 200,
        "status": "success",
        "message": "User details fetched successfully",
        "data": UserDetailResponse(**format_mongo_id(user))
    }
