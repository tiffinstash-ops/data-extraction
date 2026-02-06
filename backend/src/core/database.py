from sqlalchemy import create_engine
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import os
import logging

logger = logging.getLogger(__name__)
from .auth import get_credentials

# Database Credentials
DB_USER = "postgres"
DB_PASS = "tiffinstash2026"
DB_NAME = "postgres"
INSTANCE_CONNECTION_NAME = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 


def get_db_engine():
    credentials = get_credentials()
    connector = Connector(credentials=credentials)
    logger.info(f"Connector1: {connector}")

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC
        )
    logger.info(f"Connector2: {connector}")
    engine = create_engine("postgresql+pg8000://", creator=getconn)
    logger.info(f"Connector3: {connector}")
    return engine, connector
