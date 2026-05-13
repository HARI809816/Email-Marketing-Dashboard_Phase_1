from app.database import orders_collection

def get_user_dashboard_data(client_match: dict):
    """
    Core aggregation logic for generating user/employee dashboard statistics.
    """
    pipeline = [
        {"$match": client_match},
        {
            "$lookup": {
                "from": "orders",
                "localField": "client_id",
                "foreignField": "client_id",
                "as": "orders"
            }
        },
        {"$unwind": {"path": "$orders", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": "$_id",
                "client_id": {"$first": "$client_id"},
                "name": {"$first": "$name"},
                "country": {"$first": "$country"},
                "total_orders_count": {
                    "$sum": {"$cond": [{"$ifNull": ["$orders.order_id", False]}, 1, 0]}
                },
                "total_billed": {"$sum": {"$ifNull": ["$orders.total_amount", 0]}},
                "total_paid": {"$sum": {"$ifNull": ["$orders.paid_amount", 0]}},
                "orders_list": {
                    "$push": {
                        "$cond": [
                            {"$ifNull": ["$orders.order_id", False]},
                            {
                                "order_id": "$orders.order_id",
                                "order_status": "$orders.order_status",
                                "total_amount": "$orders.total_amount",
                                "paid_amount": "$orders.paid_amount",
                                "order_date": "$orders.order_date"
                            },
                            "$$REMOVE"
                        ]
                    }
                }
            }
        },
        {
            "$addFields": {
                "balance": {"$subtract": ["$total_billed", "$total_paid"]},
                "payment_status": {
                    "$cond": [
                        {"$eq": ["$total_orders_count", 0]}, "No Orders",
                        {"$cond": [
                            {"$lte": [{"$subtract": ["$total_billed", "$total_paid"]}, 0]}, "Paid",
                            "Pending"
                        ]}
                    ]
                }
            }
        },
        {"$sort": {"name": 1}}
    ]
    
    return list(orders_collection.aggregate(pipeline))
