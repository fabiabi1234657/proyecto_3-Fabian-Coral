from pymongo import MongoClient

def get_mongo_connection():
    client = MongoClient('mongodb://127.0.0.1:27017/')
    db = client['mercancia']
    return db
