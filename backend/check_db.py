import pandas as pd
from sqlalchemy import text
from src.core.database import get_db_engine

engine, _ = get_db_engine()
oid = '30043'
with engine.connect() as conn:
    print(f"--- FINGERPRINT FOR ORDER {oid} ---")
    res = conn.execute(text(f'SELECT "ORDER ID", "SKU", "DATE", "PRODUCT", "QUANTITY", "NAME", "DELIVERY TIME" FROM "historical-data" WHERE "ORDER ID" = :oid'), {"oid": oid})
    rows = res.fetchall()
    for row in rows:
        print(dict(row._mapping))
