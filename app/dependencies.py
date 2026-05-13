from fastapi import Depends, HTTPException, status
from app.auth import get_current_user, require_admin, require_manager_or_higher
# This file is a proxy for the logic in app/auth.py to avoid circular imports 
# or to provide a cleaner interface for routers.

# We can just re-export them or move the logic here.
# For now, let's keep them in app.auth but import them where needed.
