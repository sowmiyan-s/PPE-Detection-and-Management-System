import asyncio
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    uri = "mongodb+srv://rdxsparrowgaming_db_user:DBL67D8Qc0RcqlCf@cluster0.er22sa5.mongodb.net/?appName=Cluster0"
    
    print("Testing 1: Standard SRV with certifi")
    try:
        c1 = AsyncIOMotorClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        res = await c1.admin.command('ping')
        print("Success 1:", res)
        return
    except Exception as e:
        print("Fail 1:", e)

    print("Testing 2: tlsAllowInvalidCertificates=True without explicit tls=True")
    try:
        c2 = AsyncIOMotorClient(uri, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
        res = await c2.admin.command('ping')
        print("Success 2:", res)
        return
    except Exception as e:
        print("Fail 2:", e)

    print("Testing 3: Plain URI without extra ssl params")
    try:
        c3 = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        res = await c3.admin.command('ping')
        print("Success 3:", res)
        return
    except Exception as e:
        print("Fail 3:", e)

if __name__ == "__main__":
    asyncio.run(test())
