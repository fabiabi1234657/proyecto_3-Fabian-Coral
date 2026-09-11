import os
from pymongo import MongoClient
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

_MONGO_CLIENT = None

def get_mongo_connection():
    """Retorna la base de datos de MongoDB reutilizando el cliente en pool (singleton)."""
    global _MONGO_CLIENT
    if _MONGO_CLIENT is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
        _MONGO_CLIENT = MongoClient(mongo_uri, maxPoolSize=50, serverSelectionTimeoutMS=5000)
    db_name = os.getenv("MONGO_DB", "mercancia")
    return _MONGO_CLIENT[db_name]
