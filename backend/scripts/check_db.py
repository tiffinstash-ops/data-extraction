
import sqlalchemy
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import os

DB_USER = "postgres"
DB_PASS = "tiffinstash2026"
DB_NAME = "postgres"
INSTANCE_CONNECTION_NAME = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 
KEY_PATH = "/Users/deepshah/Downloads/tiffinstash-key.json"

def get_engine():
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    connector = Connector(credentials=credentials)

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC
        )

    return create_engine("postgresql+pg8000://", creator=getconn), connector

try:
    engine, connector = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text('SELECT * FROM "historical-data" LIMIT 1'))
        print("Columns:", result.keys())
    connector.close()
except Exception as e:
    print(f"Error: {e}")
