from fastapi import FastAPI
import logging
import os

from src.routers import orders, master_data, sellers

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tiffinstash API")

# Include Routers
app.include_router(orders.router)
app.include_router(master_data.router)
app.include_router(sellers.router)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "backend"}
