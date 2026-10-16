from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings

# MongoClient connects lazily (on first use) and manages its own connection pool,
# so one client is shared by the whole app.
mongo_client: MongoClient = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)


def get_mongo_db() -> Database:
    return mongo_client[settings.mongodb_db_name]
