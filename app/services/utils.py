from datetime import datetime
from typing import Optional, Any
import re
from fastapi import HTTPException
from app.database import users_collection
from app.schemas import UserRole

def format_mongo_id(doc):
    if not doc:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        # Keep _id for internal use if needed, or remove it for API response
    return doc

def parse_date(date_str: Any) -> Optional[datetime]:
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str
    try:
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None

def resolve_client_handler(client: dict) -> dict:
    handler_email = client.get("client_handler")
    if handler_email:
        user = users_collection.find_one({"email": handler_email}, {"full_name": 1, "_id": 0})
        if user:
            client["client_handler_name"] = user.get("full_name")
    return client

def resolve_client_handler_bulk(clients: list[dict]) -> list[dict]:
    emails = {c.get("client_handler") for c in clients if c.get("client_handler")}
    if not emails:
        return clients
        
    users = list(users_collection.find({"email": {"$in": list(emails)}}, {"email": 1, "full_name": 1, "_id": 0}))
    user_map = {u["email"]: u["full_name"] for u in users}
    
    for c in clients:
        email = c.get("client_handler")
        if email in user_map:
            c["client_handler_name"] = user_map[email]
            
    return clients

def get_user_email_by_name(name_or_email: str) -> str:
    """Helper to find user email by full_name if needed"""
    if not name_or_email:
        return None
    if "@" in name_or_email:
        return name_or_email
        
    user = users_collection.find_one({"full_name": name_or_email}, {"email": 1})
    return user["email"] if user else name_or_email

def generate_custom_id(prefix: str, collection, current_user: dict):
    """
    Generates a unique ID based on the user's assigned range.
    Format: {prefix}-{YYYY}-{num}
    """
    year = datetime.utcnow().strftime("%Y")
    
    # 1. Determine range
    if current_user["role"] == UserRole.ADMIN:
        start, end = 1, 9999
    else:
        # Default range if not set
        start = current_user.get("id_range_start", 100)
        end = current_user.get("id_range_end", 200)
    
    # 2. Find existing IDs in this range for this year
    field_name = "client_id" if prefix == "CL" else "reference_id"
    pattern = f"^{prefix}-{year}-(\\d+)$"
    
    cursor = collection.find({
        field_name: {"$regex": pattern}
    })
    
    existing_nums = []
    for doc in cursor:
        val = doc.get(field_name)
        match = re.search(f"{prefix}-{year}-(\\d+)", val)
        if match:
            num = int(match.group(1))
            if start <= num <= end:
                existing_nums.append(num)
    
    # 3. Find next available number
    if not existing_nums:
        next_num = start
    else:
        next_num = max(existing_nums) + 1
        
    if next_num > end:
        raise HTTPException(
            status_code=400,
            detail=f"Limit reached for your assigned ID range ({start}-{end}). Please contact Admin."
        )
        
    return f"{prefix}-{year}-{next_num:04d}"

def is_id_range_overlapping(start: int, end: int, exclude_email: Optional[str] = None):
    """
    Checks if a given ID range overlaps with any existing user's range.
    """
    if start is None or end is None:
        return False
        
    query = {
        "role": UserRole.EMPLOYEE,
        "id_range_start": {"$exists": True},
        "id_range_end": {"$exists": True}
    }
    if exclude_email:
        query["email"] = {"$ne": exclude_email}
        
    existing_users = users_collection.find(query)
    
    for user in existing_users:
        e_start = user.get("id_range_start")
        e_end = user.get("id_range_end")
        
        if e_start is None or e_end is None:
            continue
            
        # Check for overlap: (StartA <= EndB) and (EndA >= StartB)
        if (start <= e_end) and (end >= e_start):
            return user.get("email")
            
    return None
