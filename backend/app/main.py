from fastapi import FastAPI
import logging

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

app = FastAPI(
    title="Tiffinstash API",
    description="Backend API for Tiffinstash data extraction and management",
    version="1.0.0"
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
