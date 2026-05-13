from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import ALLOWED_ORIGINS
from app.api import auth, users, clients, orders, payments, dashboard, tools

app = FastAPI(title="Email Dashboard API")

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- PERFORMANCE MONITORING MIDDLEWARE ---
class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log slow requests (>1 second)
        if process_time > 1.0:
            print(f"Slow Request: {request.method} {request.url.path} - {process_time:.2f}s")
            
        response.headers["X-Process-Time"] = str(process_time)
        return response

app.add_middleware(PerformanceMiddleware)

# --- GLOBAL ERROR HANDLERS ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global Error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status_code": 500,
            "status": "error",
            "message": "An internal server error occurred",
            "detail": str(exc) if "localhost" in str(request.base_url) else None
        }
    )

# --- INCLUDE ROUTERS ---
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(dashboard.router)
app.include_router(tools.router)

@app.get("/", tags=["Health"])
def read_root():
    return {
        "status": "success",
        "message": "Email Dashboard API is running",
        "timestamp": time.time()
    }
