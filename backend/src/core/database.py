from sqlalchemy import create_engine
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import os

# Database Credentials
DB_USER = "postgres"
DB_PASS = "tiffinstash2026"
DB_NAME = "postgres"
INSTANCE_CONNECTION_NAME = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 
# Better to use absolute path or env var for safety
KEY_PATH = "/etc/tiffinstash-sa-key" if os.path.exists("/etc/tiffinstash-sa-key") else "/Users/deepshah/Downloads/tiffinstash-key.json"

def get_db_engine():
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

    engine = create_engine("postgresql+pg8000://", creator=getconn)
    return engine, connector
