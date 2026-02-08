from pydantic import BaseModel
from typing import Optional, Dict, List

class OrderUpdate(BaseModel):
    order_id: str
    sku: Optional[str] = None
    tl_notes: Optional[str] = None
    skus: Dict[str, str] = {}
    filters: Optional[Dict[str, str]] = None # Extra fields (Meal Type, etc) for precision

class SkipUpdate(BaseModel):
    order_id: str
    sku: Optional[str] = None
    skip_date: str

class MasterRowUpdate(BaseModel):
    order_id: str
    original_row: Dict[str, str] # Full fingerprint of the row before edit
    updates: Dict[str, str]

class MasterUploadRequest(BaseModel):
    table_name: str = "historical-data"
    data: List[Dict]
