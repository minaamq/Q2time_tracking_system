from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel
from app.database.models import BreakType

class LoginRequest(BaseModel):
    emp_id: str
    login_time: Optional[datetime] = None

class LogoutRequest(BaseModel):
    emp_id: str
    logout_time: Optional[datetime] = None

class BreakRequest(BaseModel):
    emp_id: str
    break_type: BreakType
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None

class TimeCalculationResponse(BaseModel):
    emp_id: str
    scenario: str
    login_time: Optional[datetime]
    logout_time: Optional[datetime]
    breaks: List[dict]
    total_work_hours: str
    calculation_details: dict
