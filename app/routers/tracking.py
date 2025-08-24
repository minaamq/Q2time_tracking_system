from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
import pytz

from app.models.schemas import (
    LoginRequest, LogoutRequest, BreakRequest, TimeCalculationResponse,
)
from app.services.session_manager import session_manager
from app.services.time_calculator import TimeCalculator
from app.services.geo_timezone import geo_timezone_service
from app.database.models import BreakEntry
from app.database.repository import TimeEntryRepository
from app.database.config import get_database

router = APIRouter(prefix="/api/v1", tags=["time-tracking"])

#--------------------Helpers                                                                     #

def _to_utc_naive(dt: datetime, user_tz: str) -> datetime:

    if dt.tzinfo is None:                             
        dt = pytz.timezone(user_tz).localize(dt)
    return dt.astimezone(pytz.UTC).replace(tzinfo=None)


def _to_user_zone(dt: datetime, user_tz: str) -> datetime:
    return pytz.UTC.localize(dt).astimezone(pytz.timezone(user_tz))

#--------------------Login-----------#

@router.post("/login")
async def login(request: LoginRequest, req: Request):
    ip           = geo_timezone_service.get_client_ip(req)
    user_tz, loc = await geo_timezone_service.get_timezone_from_ip(ip)

    login_time = request.login_time or geo_timezone_service.get_current_time_in_timezone(user_tz)
    login_time = _to_utc_naive(login_time, user_tz)

    await session_manager.create_or_update_session(
        emp_id=request.emp_id, request=req, login_time=login_time
    )

    return {
        "message": "Login successful",
        "emp_id":  request.emp_id,
        "login_time": _to_user_zone(login_time, user_tz),
        "timezone":  user_tz,
        "location":  loc,
        "ip_address": ip,
    }


#----Logout--------#

@router.post("/logout")
async def logout(request: LogoutRequest, req: Request):
    session = await session_manager.get_current_session(request.emp_id)
    if not session:
        raise HTTPException(404, "No active session found")

    user_tz = session.timezone or "UTC"

    logout_time = request.logout_time or geo_timezone_service.get_current_time_in_timezone(user_tz)
    logout_time = _to_utc_naive(logout_time, user_tz)

    await session_manager.create_or_update_session(
        emp_id=request.emp_id, request=req, logout_time=logout_time
    )

    return {
        "message":    "Logout successful",
        "emp_id":     request.emp_id,
        "logout_time": _to_user_zone(logout_time, user_tz),
        "timezone":    user_tz,
    }

#------ Break-----#

@router.post("/break")
async def record_break(request: BreakRequest, req: Request):
    session = await session_manager.get_current_session(request.emp_id)
    if not session:
        raise HTTPException(404, "No active session found")

    user_tz = session.timezone or "UTC"

    # ---- normalising timestamps ------------------------------------------------
    start_utc = _to_utc_naive(request.start_time, user_tz) if request.start_time else None
    end_utc   = _to_utc_naive(request.end_time,   user_tz) if request.end_time   else None

    # auto duration
    duration = request.duration_minutes
    if start_utc and end_utc and duration is None:
        duration = int((end_utc - start_utc).total_seconds() / 60)

    break_entry = BreakEntry(
        break_type       = request.break_type,
        start_time       = start_utc,
        end_time         = end_utc,
        duration_minutes = duration,
        timezone         = user_tz,
    )

    # one mandatory break of each type per day
    if break_entry.break_type.value != "bio":
        if break_entry.break_type in [b.break_type for b in session.breaks]:
            raise HTTPException(
                400, f"{break_entry.break_type} already recorded for today"
            )

    # overlap check
    test_breaks = session.breaks + [break_entry]
    has_overlap, details = TimeCalculator.check_overlapping_breaks(test_breaks)
    if has_overlap:
        return {
            "message": "Break recorded with overlap warning",
            "warning": details,
            "overlap_detected": True,
        }

    await session_manager.create_or_update_session(
        emp_id=request.emp_id, request=req, breaks=[break_entry]
    )

    return {
        "message":  "Break recorded successfully",
        "break_type": request.break_type,
        "duration_minutes": duration,
        "start_time": _to_user_zone(start_utc, user_tz) if start_utc else None,
        "end_time":   _to_user_zone(end_utc,   user_tz) if end_utc   else None,
        "timezone":   user_tz,
    }


#------- Calculate hours ------#
@router.get("/calculate/{emp_id}", response_model=TimeCalculationResponse)
async def calculate_hours(emp_id: str):
    session = await session_manager.get_current_session(emp_id)
    if not session:
        raise HTTPException(404, "No session found for employee")

    hrs, details, scenario = TimeCalculator.calculate_work_hours(session)

    # hh:mm formatting
    if hrs == 0:
        hrs_str = "Absent"
    else:
        h, m = divmod(int(round(hrs * 60)), 60)
        hrs_str = f"{h}:{m:02d}hrs" if m else f"{h} hrs"

    breaks_info = [
        {
            "type":      b.break_type,
            "duration":  f"{b.duration_minutes}min" if b.duration_minutes else "Null",
            "start_time": b.start_time,
            "end_time":   b.end_time,
        }
        for b in session.breaks
    ]

    return TimeCalculationResponse(
        emp_id           = emp_id,
        scenario         = scenario,
        login_time       = session.login_time,
        logout_time      = session.logout_time,
        breaks           = breaks_info,
        total_work_hours = hrs_str,
        calculation_details = details,
    )


#--Utilities-------#

@router.get("/sessions")
async def get_all_sessions():
    db = await get_database()
    repo = TimeEntryRepository(db)
    sessions = await repo.get_all_entries()
    return {"sessions": [s.dict(by_alias=True) for s in sessions]}


@router.get("/timezone-info")
async def get_timezone_info(req: Request):
    ip   = geo_timezone_service.get_client_ip(req)
    tz, loc = await geo_timezone_service.get_timezone_from_ip(ip)
    now  = geo_timezone_service.get_current_time_in_timezone(tz)
    return {"ip_address": ip, "timezone": tz, "current_time": now, "location": loc}


@router.post("/validate-break")
async def validate_break_timing(request: BreakRequest):
    session = await session_manager.get_current_session(request.emp_id)
    if not session:
        raise HTTPException(404, "No active session found")

    user_tz = session.timezone or "UTC"
    temp_entry = BreakEntry(
        break_type       = request.break_type,
        start_time       = _to_utc_naive(request.start_time, user_tz) if request.start_time else None,
        end_time         = _to_utc_naive(request.end_time,   user_tz) if request.end_time   else None,
        duration_minutes = request.duration_minutes,
    )

    overlaps, details = TimeCalculator.check_overlapping_breaks(session.breaks + [temp_entry])
    return {"valid": not overlaps, "overlap_detected": overlaps, "overlap_details": details}
