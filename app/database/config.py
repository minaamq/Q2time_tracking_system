import os
import certifi
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

class Database:
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def get_database():
    return db.database

async def connect_to_mongo(
    uri: str | None = None,
    db_name: str | None = None,
    attempts: int = 3
):

    mongodb_url = uri or os.getenv("MONGODB_URL")
    database_name = db_name or os.getenv("DATABASE_NAME", "time_tracking_system")
    app_name = os.getenv("APP_NAME", "time-tracker")

    if not mongodb_url:
        raise ValueError("MONGODB_URL is not set in environment")

    opts = {
        "tls": True,
        "tlsCAFile": certifi.where(),
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 10000,
        "retryWrites": True,
        "appname": app_name,
    }

    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            print(f"Trying MongoDB connection (attempt {attempt})...")
            db.client = AsyncIOMotorClient(mongodb_url, **opts)
            db.database = db.client[database_name]

           
            await db.client.admin.command("ping")
            print("Connected to MongoDB")
            await create_indexes()
            return

        except Exception as e:
            last_exc = e
            print(f"Attempt {attempt} failed: {e}")
            try:
                if db.client:
                    db.client.close()
            except Exception:
                pass
            db.client = None
            db.database = None

            if attempt < attempts:
                backoff = 2 ** attempt
                print(f"Retrying in {backoff}s...")
                await asyncio.sleep(backoff)

    raise Exception("Could not connect to MongoDB after retries") from last_exc

async def create_indexes():

    try:
        collection = db.database.time_entries
        #  unique index for (emp_id, date)
        await collection.create_index([("emp_id", 1), ("date", 1)], unique=True)
        await collection.create_index([("emp_id", 1)])
        await collection.create_index([("date", 1)])
        print("Indexes ensured")
    except Exception as e:
        print(f"Warning: index creation failed: {e}")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        db.client = None
        db.database = None
        print("MongoDB connection closed")
