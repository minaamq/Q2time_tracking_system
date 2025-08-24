from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import tracking
from app.database.config import connect_to_mongo, close_mongo_connection
from app.services.session_manager import session_manager
from app.database.models import TimeEntry, BreakEntry, BreakType
from datetime import datetime, date
import pytz

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Time Tracking System.")
    await connect_to_mongo()
    await initialize_test_data()
    print("Time Tracking System ready!")
    yield
    # Shutdown
    print("Shutting down Time Tracking System.")
    await close_mongo_connection()

app = FastAPI(
    title="Time Tracking System",
    description="Employee tracking system",
    lifespan=lifespan
)

# Adding CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tracking.router)

async def initialize_test_data():

    

    try:
        from app.database.config import get_database
        database = await get_database()
        collection = database.time_entries
        
        # Remove existing test data
        test_emp_ids = ["Emp123", "Emp564", "Emp567", "Emp239", "Emp999"]
        for emp_id in test_emp_ids:
            await collection.delete_many({"emp_id": emp_id})
        
        print("Cleared existing test data")
    except Exception as e:
        print(f"Note: Could not clear existing data: {e}")
    
    # Special test cases representing full workdays(9AM-6PM)
    # These arehandled differently than partial days
    full_day_test_cases = [
        # Test Case 1, Normal full-day calculation
        {
            "emp_id": "Emp123",
            "date": datetime(2025, 8, 24),
            "login_time": datetime(2025, 8, 23, 9, 0),
            "logout_time": datetime(2025, 8, 23, 18, 0),
            "timezone": "Asia/Kolkata",
            "is_full_workday": True,  # Special flag
            "breaks": [
                BreakEntry(break_type=BreakType.BREAK1, duration_minutes=30),
                BreakEntry(break_type=BreakType.BREAK2, duration_minutes=30),
                BreakEntry(break_type=BreakType.BIO, duration_minutes=10)
            ]
        },
        # Test Case 2 Full-day, forgot to logout
        {
            "emp_id": "Emp564",
            "date": datetime(2025, 8, 24),
            "login_time": datetime(2025, 8, 23, 9, 0),
            "logout_time": None,  # Will default to 6 PM
            "timezone": "America/New_York",
            "is_full_workday": True,
            "breaks": [
                BreakEntry(break_type=BreakType.BREAK1, duration_minutes=40),
                BreakEntry(break_type=BreakType.BREAK2, duration_minutes=20),
                BreakEntry(break_type=BreakType.BIO, duration_minutes=5)
            ]
        },
        # Test Case 3: Forgot to login
        {
            "emp_id": "Emp567",
            "date": datetime(2025, 8, 24),
            "login_time": None,
            "logout_time": None,
            "timezone": "UTC",
            "breaks": []
        },
        # Test Case 4: Full-day, exceeds break time
        {
            "emp_id": "Emp239", 
            "date": datetime(2025, 8, 24),
            "login_time": datetime(2025, 8, 23, 9, 0),
            "logout_time": datetime(2025, 8, 23, 18, 0),
            "timezone": "Europe/London",
            "is_full_workday": True,
            "breaks": [
                BreakEntry(break_type=BreakType.BREAK1, duration_minutes=35),
                BreakEntry(break_type=BreakType.BREAK2, duration_minutes=40),
                BreakEntry(break_type=BreakType.BIO, duration_minutes=30)
            ]
        }
    ]
     
    # Creating test data
    for test_case in full_day_test_cases:
        try:
            new_session = TimeEntry(**test_case)
            from app.database.config import get_database
            database = await get_database()
            collection = database.time_entries
            
            session_dict = new_session.dict(by_alias=True, exclude_unset=True)
            if 'date' in session_dict and isinstance(session_dict['date'], date):
                session_dict['date'] = datetime(
                    session_dict['date'].year,
                    session_dict['date'].month, 
                    session_dict['date'].day
                )
            
            await collection.insert_one(session_dict)
            print(f"Created test data for {test_case['emp_id']}")
        except Exception as e:
            print(f"Error creating test data for {test_case['emp_id']}: {e}")


