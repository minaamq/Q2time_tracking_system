from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class BreakType(str, Enum):
    BREAK1 = "break1"
    BREAK2 = "break2"
    BIO = "bio"

class BreakEntry(BaseModel):
    break_type: BreakType
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    timezone: Optional[str] = "UTC"
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v and 'start_time' in values and values['start_time']:
            if v <= values['start_time']:
                raise ValueError("End time must be after start time")
        return v
    
    @validator('duration_minutes', pre=True, always=True)
    def calculate_duration(cls, v, values):
        if v is not None:
            return v
        if 'start_time' in values and 'end_time' in values:
            start = values['start_time']
            end = values['end_time']
            if start and end:
                return int((end - start).total_seconds() / 60)
        return v

class TimeEntry(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    emp_id: str
    date: datetime
    login_time: Optional[datetime] = None
    logout_time: Optional[datetime] = None
    breaks: List[BreakEntry] = []
    total_work_hours: Optional[float] = None
    scenario: Optional[str] = None
    timezone: str = "UTC"
    ip_address: Optional[str] = None
    location: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('date', pre=True)
    def convert_date_to_datetime(cls, v):
        """Convert date to datetime at midnight UTC"""
        if isinstance(v, date) and not isinstance(v, datetime):
            return datetime(v.year, v.month, v.day)
        return v
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
