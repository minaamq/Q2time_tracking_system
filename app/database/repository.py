from datetime import date, datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database.models import TimeEntry
from app.database.config import get_database

class TimeEntryRepository:
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.time_entries

    def _convert_date_to_datetime(self, entry_date: date) -> datetime:
        """Convert date to datetime at midnight UTC"""
        if isinstance(entry_date, date) and not isinstance(entry_date, datetime):
            return datetime(entry_date.year, entry_date.month, entry_date.day)
        return entry_date

    async def create_time_entry(self, time_entry: TimeEntry) -> TimeEntry:
        """Create a new time entry"""
        entry_dict = time_entry.dict(by_alias=True, exclude_unset=True)
        if 'date' in entry_dict:
            entry_dict['date'] = self._convert_date_to_datetime(entry_dict['date'])
        
        result = await self.collection.insert_one(entry_dict)
        time_entry.id = result.inserted_id
        return time_entry

    async def get_time_entry(self, emp_id: str, entry_date: date) -> Optional[TimeEntry]:
        """Getingtime entry for employee on specific date"""
        # Converting date to datetime for MongoDB query
        search_date = self._convert_date_to_datetime(entry_date)
        
        entry = await self.collection.find_one({
            "emp_id": emp_id,
            "date": search_date
        })
        if entry:
            return TimeEntry(**entry)
        return None

    async def update_time_entry(self, emp_id: str, entry_date: date, update_data: dict) -> Optional[TimeEntry]:
        search_date = self._convert_date_to_datetime(entry_date)
        
        # Converting any date fields in update_data
        if 'date' in update_data:
            update_data['date'] = self._convert_date_to_datetime(update_data['date'])
        
        result = await self.collection.find_one_and_update(
            {"emp_id": emp_id, "date": search_date},
            {"$set": update_data},
            return_document=True
        )
        if result:
            return TimeEntry(**result)
        return None

    async def get_all_entries(self) -> list:
        """Get all time entries"""
        cursor = self.collection.find({})
        entries = []
        async for entry in cursor:
            entries.append(TimeEntry(**entry))
        return entries

    async def delete_time_entry(self, emp_id: str, entry_date: date) -> bool:
        """Delete time entry"""
        search_date = self._convert_date_to_datetime(entry_date)
        
        result = await self.collection.delete_one({
            "emp_id": emp_id,
            "date": search_date
        })
        return result.deleted_count > 0
