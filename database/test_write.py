import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URI = "mongodb+srv://rdxsparrowgaming_db_user:DBL67D8Qc0RcqlCf@cluster0.er22sa5.mongodb.net/?appName=Cluster0"

async def test_write():
    try:
        print("Connecting...")
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client["edgevision"]
        print("Inserting document...")
        res = await db.test_collection.insert_one({"test": "data"})
        print(f"Insert successful! ID: {res.inserted_id}")
    except Exception as e:
        print(f"Error during insert: {e}")

if __name__ == "__main__":
    asyncio.run(test_write())
