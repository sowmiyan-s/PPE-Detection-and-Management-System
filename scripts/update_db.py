import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
    db = client['edgevision']
    try:
        await db.cameras.update_many({}, {'$set': {'source': '0', 'streamUrl': '0', 'type': 'webcam', 'is_active': 1}})
        print('Updated cameras in DB')
    except Exception as e:
        print(f"Error updating DB: {e}")

asyncio.run(run())
