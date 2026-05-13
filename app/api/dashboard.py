from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    DashboardOrderResponse, DashboardUpdate, UnifiedCreateRequest, 
    ApiResponse, UserRole
)
from app.auth import get_current_user
from app.database import (
    clients_collection, orders_collection, manuscripts_collection, 
    payments_collection, payment_history_collection
)
from app.services.utils import (
    generate_custom_id, format_mongo_id, parse_date, get_user_email_by_name
)
from datetime import datetime
from bson import ObjectId
from typing import List

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard/orders", response_model=ApiResponse[List[DashboardOrderResponse]])
def get_dashboard_orders(current_user: dict = Depends(get_current_user)):
    client_match = {}
    if current_user["role"] == UserRole.EMPLOYEE:
        client_match = {"client_handler": current_user.get("email")}
        
    pipeline = [
        {"$match": client_match},
        {
            "$lookup": {
                "from": "orders",
                "localField": "client_id",
                "foreignField": "client_id",
                "as": "order"
            }
        },
        {"$unwind": {"path": "$order", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "payments",
                "localField": "order.order_id",
                "foreignField": "order_id",
                "as": "p_list"
            }
        },
        {
            "$project": {
                "_id": 0,
                "order_db_id": {"$cond": [{"$ifNull": ["$order._id", False]}, {"$toString": "$order._id"}, None]},
                "order_id": "$order.order_id",
                "s_no": "$order.s_no",
                "order_date": "$order.order_date",
                "client_id": "$client_id",
                "client_name": "$name",
                "client_country": "$country",
                "client_Email": "$email",
                "client_whatsapp_number": "$whatsapp_no",
                "reference_id": "$order.reference_id",
                "ref_no": {"$ifNull": ["$order.client_ref_no", "$client_ref_no"]},
                "manuscript_id": "$order.manuscript_id",
                "journal_name": "$order.journal_name",
                "title": "$order.title",
                "order_type": "$order.order_type",
                "index": "$order.index",
                "rank": "$order.rank",
                "currency": {"$ifNull": ["$order.currency", "USD"]},
                "total_amount": {"$ifNull": ["$order.total_amount", 0.0]},
                "writing_amount": {"$ifNull": ["$order.writing_amount", 0.0]},
                "modification_amount": {"$ifNull": ["$order.modification_amount", 0.0]},
                "po_amount": {"$ifNull": ["$order.po_amount", 0.0]},
                "writing_start_date": "$order.writing_start_date",
                "writing_end_date": "$order.writing_end_date",
                "modification_start_date": "$order.modification_start_date",
                "modification_end_date": "$order.modification_end_date",
                "po_start_date": "$order.po_start_date",
                "po_end_date": "$order.po_end_date",
                "phase": {"$literal": None},
                "phase_1_payment": {"$arrayElemAt": ["$p_list.phase_1_payment", 0]},
                "phase_1_payment_date": {"$arrayElemAt": ["$p_list.phase_1_payment_date", 0]},
                "phase_1_payment_details": {"$arrayElemAt": ["$p_list.phase_1_payment_details", 0]},
                "phase_2_payment": {"$arrayElemAt": ["$p_list.phase_2_payment", 0]},
                "phase_2_payment_date": {"$arrayElemAt": ["$p_list.phase_2_payment_date", 0]},
                "phase_2_payment_details": {"$arrayElemAt": ["$p_list.phase_2_payment_details", 0]},
                "phase_3_payment": {"$arrayElemAt": ["$p_list.phase_3_payment", 0]},
                "phase_3_payment_date": {"$arrayElemAt": ["$p_list.phase_3_payment_date", 0]},
                "phase_3_payment_details": {"$arrayElemAt": ["$p_list.phase_3_payment_details", 0]},
                "payment_status": {"$ifNull": ["$order.payment_status", "Pending"]},
                "paid_amount": {"$ifNull": ["$order.paid_amount", 0.0]},
                "remarks": "$order.remarks",
                "order_status": "$order.order_status",
                "client_drive_link": "$client_drive_link",
                "payment_drive_link": "$order.payment_drive_link",
                "clients_details": "$order.clients_details"
            }
        }
    ]
    
    results = list(clients_collection.aggregate(pipeline))
    return {
        "status_code": 200,
        "status": "success",
        "message": "Dashboard orders fetched successfully",
        "data": [DashboardOrderResponse(**r) for r in results]
    }

@router.patch("/dashboard/orders/{order_db_id}", response_model=ApiResponse[dict])
def update_dashboard_order(order_db_id: str, update_data: DashboardUpdate, current_user: dict = Depends(get_current_user)):
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return {"status_code": 200, "status": "success", "message": "No changes provided"}

    client_fields = ["client_id", "client_country", "client_Email", "client_whatsapp_number", "client_link", "bank_account", "client_affiliations"]
    order_fields = ["manuscript_id", "order_date", "reference_id", "ref_no", "journal_name", "title", "order_type", "index", "rank", "currency", "total_amount", "writing_amount", "modification_amount", "po_amount", "writing_start_date", "writing_end_date", "modification_start_date", "modification_end_date", "po_start_date", "po_end_date", "payment_status", "remarks", "order_status", "payment_drive_link", "paid_amount", "clients_details", "client_details", "client_drive_link", "is_new_order"]
    payment_fields = ["phase_1_payment", "phase_1_payment_date", "phase_1_payment_details", "phase_2_payment", "phase_2_payment_date", "phase_2_payment_details", "phase_3_payment", "phase_3_payment_date", "phase_3_payment_details","payment_status", "paid_amount"]

    try:
        order = orders_collection.find_one({"_id": ObjectId(order_db_id)})
    except Exception:
         raise HTTPException(status_code=400, detail="Invalid order_db_id format")
         
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    old_client_id = order["client_id"]
    order_custom_id = order["order_id"]

    # 3. Perform Updates
    client_updates = {f: update_dict[f] for f in client_fields if f in update_dict}
    if client_updates:
        new_client_id = client_updates.get("client_id")
        mapping = {
            "client_id": "client_id",
            "client_country": "country",
            "client_Email": "email",
            "client_whatsapp_number": "whatsapp_no",
            "client_link": "client_link",
            "bank_account": "bank_account",
            "client_affiliations": "affiliation"
        }
        mapped_client_updates = {mapping.get(k, k): v for k, v in client_updates.items()}
        clients_collection.update_one({"client_id": old_client_id}, {"$set": mapped_client_updates})

        if new_client_id and new_client_id != old_client_id:
            orders_collection.update_many({"client_id": old_client_id}, {"$set": {"client_id": new_client_id}})
            payments_collection.update_many({"client_id": old_client_id}, {"$set": {"client_id": new_client_id}})
            manuscripts_collection.update_many({"client_id": old_client_id}, {"$set": {"client_id": new_client_id}})
            old_client_id = new_client_id

    order_updates = {f: update_dict[f] for f in order_fields if f in update_dict}
    if order_updates:
        mapped_order_updates = {}
        mapping = {"ref_no": "client_ref_no", "client_details": "clients_details"}
        for k, v in order_updates.items():
            mapped_order_updates[mapping.get(k, k)] = v
        mapped_order_updates["updated_at"] = datetime.utcnow()
        if "order_date" in mapped_order_updates:
            mapped_order_updates["order_date"] = parse_date(mapped_order_updates["order_date"])
        orders_collection.update_one({"_id": ObjectId(order_db_id)}, {"$set": mapped_order_updates})

    payment_updates_raw = {f: update_dict[f] for f in payment_fields if f in update_dict}
    if payment_updates_raw:
        payments_collection.update_one({"order_id": order_custom_id}, {"$set": payment_updates_raw}, upsert=True)
        history_record = payment_updates_raw.copy()
        history_record.update({
            "client_id": old_client_id,
            "order_id": order_custom_id,
            "reference_id": order.get("reference_id"),
            "created_at": datetime.utcnow()
        })
        payment_history_collection.insert_one(history_record)

    return {"status_code": 200, "status": "success", "message": "Dashboard order updated successfully"}

@router.post("/unified/create", response_model=ApiResponse[dict], status_code=status.HTTP_201_CREATED)
def create_unified_record(request: UnifiedCreateRequest, current_user: dict = Depends(get_current_user)):
    if not request.client_id and not clients_collection.find_one({"name": request.client_name}):
        request.client_id = generate_custom_id("CL", clients_collection, current_user)
    
    if not request.reference_id:
        request.reference_id = generate_custom_id("REF", orders_collection, current_user)

    existing_client = clients_collection.find_one({"client_id": request.client_id}) if request.client_id else clients_collection.find_one({"name": request.client_name})

    if not existing_client:
        client_data = {
            "client_id": request.client_id,
            "name": request.client_name,
            "country": request.client_country,
            "email": request.client_email,
            "whatsapp_no": request.client_whatsapp_no,
            "client_ref_no": request.client_ref_no,
            "client_link": request.client_link,
            "bank_account": request.client_bank_account,
            "affiliation": request.client_affiliation,
            "payment_drive_link": request.payment_drive_link,
            "client_drive_link": request.client_drive_link,
            "total_orders": 0,
            "client_handler": current_user.get("email") if current_user["role"] == UserRole.EMPLOYEE else get_user_email_by_name(request.client_handler),
            "created_at": datetime.utcnow()
        }
        clients_collection.insert_one(client_data)
        client_id = request.client_id
        client_payment_drive_link = request.payment_drive_link
    else:
        client_id = existing_client["client_id"]
        client_payment_drive_link = existing_client.get("payment_drive_link")

    manuscript_id = None
    if request.create_manuscript and request.manuscript_title:
        manuscript_data = {
            "manuscript_id": f"MS-{client_id}-{request.reference_id}",
            "title": request.manuscript_title,
            "journal_name": request.manuscript_journal_name or request.journal_name,
            "order_type": request.order_type,
            "client_id": client_id,
            "created_at": datetime.utcnow()
        }
        manuscripts_collection.insert_one(manuscript_data)
        manuscript_id = manuscript_data["manuscript_id"]

    global_order_count = orders_collection.count_documents({}) + 1
    order_id = f"ORD-{datetime.utcnow().strftime('%Y')}-{global_order_count:03d}"
    while orders_collection.find_one({"order_id": order_id}):
        global_order_count += 1
        order_id = f"ORD-{datetime.utcnow().strftime('%Y')}-{global_order_count:03d}"

    if orders_collection.find_one({"reference_id": request.reference_id}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Reference ID '{request.reference_id}' already exists")

    order_data = {
        "order_id": order_id,
        "reference_id": request.reference_id,
        "profile_name": request.profile_name,
        "client_ref_no": request.client_ref_no,
        "s_no": global_order_count,
        "order_date": parse_date(request.order_date),
        "client_id": client_id,
        "manuscript_id": manuscript_id,
        "journal_name": request.journal_name,
        "title": request.title,
        "order_type": request.order_type,
        "index": request.index,
        "rank": request.rank,
        "currency": request.currency or "USD",
        "total_amount": request.total_amount or 0,
        "writing_amount": request.writing_amount or 0,
        "modification_amount": request.modification_amount or 0,
        "po_amount": request.po_amount or 0,
        "writing_start_date": parse_date(request.writing_start_date) or parse_date(request.write_start_date),
        "writing_end_date": parse_date(request.writing_end_date),
        "modification_start_date": parse_date(request.modification_start_date),
        "modification_end_date": parse_date(request.modification_end_date),
        "po_start_date": parse_date(request.po_start_date),
        "po_end_date": parse_date(request.po_end_date),
        "payment_status": request.payment_status or "Pending",
        "order_status": "Active",
        "payment_drive_link": request.payment_drive_link or client_payment_drive_link,
        "clients_details": request.clients_details or getattr(request, 'client_details', None),
        "client_drive_link": request.client_drive_link,
        "is_new_order": request.is_new_order or "yes",
        "remarks": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    orders_collection.insert_one(order_data)

    payment_created = False
    if request.create_payment and request.payment_amount:
        payment_data = {
            "client_ref_number": request.client_ref_no,
            "reference_id": request.reference_id,
            "client_id": client_id,
            "order_id": order_id,
            "phase": request.payment_phase or 1,
            "amount": request.payment_amount,
            "payment_received_account": request.payment_received_account,
            "payment_date": parse_date(request.payment_date) or datetime.utcnow(),
            "status": "paid",
            "paid_amount": request.payment_amount,
            "created_at": datetime.utcnow()
        }
        phase = payment_data["phase"]
        payment_data[f"phase_{phase}_payment"] = request.payment_amount
        payment_data[f"phase_{phase}_payment_date"] = payment_data["payment_date"]
        payments_collection.insert_one(payment_data)

        history_item = {
            "client_name": request.client_name,
            "client_id": client_id,
            "order_id": order_id,
            "reference_id": request.reference_id,
            "amount": request.total_amount or request.payment_amount,
            "paid_amount": request.payment_amount,
            "payment_date": payment_data["payment_date"],
            "payment_received_account": request.payment_received_account,
            "order_title": request.title or "Unknown Title",
            "phase_1_payment": payment_data.get("phase_1_payment", 0.0),
            "phase_1_payment_date": payment_data.get("phase_1_payment_date"),
            "phase_2_payment": payment_data.get("phase_2_payment", 0.0),
            "phase_2_payment_date": payment_data.get("phase_2_payment_date"),
            "phase_3_payment": payment_data.get("phase_3_payment", 0.0),
            "phase_3_payment_date": payment_data.get("phase_3_payment_date"),
            "created_at": datetime.utcnow()
        }
        payment_history_collection.insert_one(history_item)
        if not order_data.get("total_amount"):
            orders_collection.update_one({"order_id": order_id}, {"$set": {"total_amount": request.payment_amount}})
        payment_created = True

    clients_collection.update_one({"client_id": client_id}, {"$inc": {"total_orders": 1}})

    return {
        "status_code": 201,
        "status": "success",
        "message": "Unified record created successfully",
        "data": {
            "client_id": client_id,
            "order_id": order_id,
            "reference_id": request.reference_id,
            "manuscript_id": manuscript_id,
            "payment_created": payment_created,
            "client_created": existing_client is None
        }
    }
