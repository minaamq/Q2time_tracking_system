from datetime import datetime, date
from typing import Optional
import pytz
from app.database.models import TimeEntry, BreakEntry
from app.database.repository import TimeEntryRepository
from app.database.config import get_database
from app.services.geo_timezone import geo_timezone_service
from fastapi import Request

class SessionManager:
    def __init__(self):
        self.repository = None

    async def get_repository(self):
        if not self.repository:
            database = await get_database()
            self.repository = TimeEntryRepository(database)
        return self.repository

    async def get_current_session(self, emp_id: str, current_date: date = None) -> Optional[TimeEntry]:
        """Get current session for employee"""
        if not current_date:
            current_date = datetime.now().date()
        
        repo = await self.get_repository()
        return await repo.get_time_entry(emp_id, current_date)

    async def create_or_update_session(self, emp_id: str, request: Request = None, **kwargs) -> TimeEntry:
        current_date = datetime.now().date()
        repo = await self.get_repository()
        
        # Get timezone and location info if request is provided
        timezone_str = "UTC"
        location_info = None
        ip_address = None
        
        if request:
            ip_address = geo_timezone_service.get_client_ip(request)
            timezone_str, location_info = await geo_timezone_service.get_timezone_from_ip(ip_address)
        
        # Trying to get existing session
        existing_session = await repo.get_time_entry(emp_id, current_date)
        
        if existing_session:
            # Updating existing session
            for key, value in kwargs.items():
                if key == "breaks" and value:

                    for new_break in value:
                        # Checking if break of same type already exists (except bio breaks)
                        if new_break.break_type.value == "bio":
                            # Bio breaks aremultiple
                            existing_session.breaks.append(new_break)
                        else:
                            # For break1 and break2, replace if exists
                            existing_break_found = False
                            for i, existing_break in enumerate(existing_session.breaks):
                                if existing_break.break_type == new_break.break_type:
                                    existing_session.breaks[i] = new_break
                                    existing_break_found = True
                                    break
                            if not existing_break_found:
                                existing_session.breaks.append(new_break)
                else:
                    setattr(existing_session, key, value)
            
            # Updating timezone and location info
            existing_session.timezone = timezone_str
            if location_info:
                existing_session.location = location_info
            if ip_address:
                existing_session.ip_address = ip_address
            

            update_data = existing_session.dict(exclude={"id", "created_at"}, by_alias=True)
            if 'date' in update_data and isinstance(update_data['date'], date):
                update_data['date'] = datetime(
                    update_data['date'].year, 
                    update_data['date'].month, 
                    update_data['date'].day
                )
            
            return await repo.update_time_entry(emp_id, current_date, update_data)
        else:
            # Creating new session with datetime conversion
            session_data = {
                "emp_id": emp_id,
                "date": datetime(current_date.year, current_date.month, current_date.day),
                "timezone": timezone_str,
                "ip_address": ip_address,
                "location": location_info,
                "breaks": [],
                **kwargs
            }
            
            new_session = TimeEntry(**session_data)
            return await repo.create_time_entry(new_session)

    @staticmethod
    def get_timezone_aware_time(timezone_str: str = "UTC") -> datetime:
        """Get timezone aware current time"""
        return geo_timezone_service.get_current_time_in_timezone(timezone_str)

session_manager = SessionManager()
