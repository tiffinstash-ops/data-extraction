from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import os
import secrets

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import Routers
from src.routers.orders import router as orders_router
from src.routers.sellers import router as sellers_router
from src.routers.master_data import router as master_router

# Security
security = HTTPBasic()

# Admin Credentials
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic Auth credentials against superuser credentials."""
    correct_username = secrets.compare_digest(credentials.username, SUPERUSER_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, SUPERUSER_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(
    title="Tiffinstash API",
    description="Backend API for Tiffinstash data extraction and management",
    version="1.0.0",
    dependencies=[Depends(verify_credentials)]  # Global authentication
)

# Register Routers
app.include_router(orders_router, tags=["Orders"])
app.include_router(sellers_router, tags=["Sellers"])
app.include_router(master_router, tags=["Master Data"])

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint to check API health."""
    return {
        "message": "Welcome to Tiffinstash API",
        "status": "online",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
