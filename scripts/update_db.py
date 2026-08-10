import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
    db = client['edgevision']
    try:
        await db.cameras.update_many({}, {'$set': {'source': 'test_mjpg.avi', 'streamUrl': 'test_mjpg.avi', 'type': 'webcam', 'is_active': 1}})
        print('Updated cameras in DB')
    except Exception as e:
        print(f"Error updating DB: {e}")

asyncio.run(run())
