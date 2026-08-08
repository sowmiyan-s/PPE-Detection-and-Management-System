import asyncio
import ssl
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb+srv://rdxsparrowgaming_db_user:DBL67D8Qc0RcqlCf@cluster0.er22sa5.mongodb.net/edgevision?retryWrites=true&w=majority"

import pytest

@pytest.mark.asyncio
async def test_write():
    try:
        print("Creating TLSv1.2 SSL context...")
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        print("Connecting to MongoDB Atlas...")
        client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            tls=True,
            tlsAllowInvalidCertificates=True,
        )
        db = client["edgevision"]
        print("Inserting document...")
        res = await db.test_collection.insert_one({"test": "data_success"})
        print(f"ATLAS INSERT SUCCESSFUL! ID: {res.inserted_id}")
    except Exception as e:
        print(f"Error during insert: {e}")

if __name__ == "__main__":
    asyncio.run(test_write())
