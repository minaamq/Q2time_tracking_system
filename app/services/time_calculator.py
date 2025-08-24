from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from app.database.models import TimeEntry, BreakEntry, BreakType


class TimeCalculator:
    STANDARD_WORK_HOURS      = 9     # full day reference
    MANDATORY_BREAK_MINUTES  = 30    # per break1/break2
    MAX_BIO_BREAK_MINUTES    = 30    # bio break cap
    DEFAULT_LOGOUT_HOUR      = 18    # fallback 6 PM

    @staticmethod
    def check_overlapping_breaks(breaks: List[BreakEntry]) -> Tuple[bool, Optional[str]]:
        """True/str description if any two breaks overlap."""
        overlapping = []
        timed = [(i, b) for i, b in enumerate(breaks) if b.start_time and b.end_time]

        for i, (idx1, br1) in enumerate(timed):
            for idx2, br2 in timed[i + 1 :]:
                if br1.end_time <= br2.start_time or br2.end_time <= br1.start_time:
                    continue

                ov_start = max(br1.start_time, br2.start_time)
                ov_end   = min(br1.end_time,   br2.end_time)
                ov_min   = (ov_end - ov_start).total_seconds() / 60

                overlapping.append(
                    f"{br1.break_type}({idx1+1}) overlaps {br2.break_type}({idx2+1}) "
                    f"for {ov_min:.0f} min"
                )

        return (True, "; ".join(overlapping)) if overlapping else (False, None)

    @staticmethod
    def handle_overlapping_breaks(breaks: List[BreakEntry]) -> Tuple[List[BreakEntry], dict]:
        has, msg = TimeCalculator.check_overlapping_breaks(breaks)
        return breaks, {
            "has_overlaps": has,
            "overlap_details": msg,
            "adjustments_made": []   
        }

    @staticmethod
    def calculate_work_hours(time_entry: TimeEntry) -> Tuple[float, dict, str]:
        """Returns (hours, calculation_details, scenario)"""

        if not time_entry.login_time:  # no login
            return 0.0, {"error": "No login time recorded"}, "Absent"

        # assume 18:00 if no logout
        logout_time = time_entry.logout_time or time_entry.login_time.replace(
            hour=TimeCalculator.DEFAULT_LOGOUT_HOUR, minute=0, second=0)
        scenario = "Calculation" if time_entry.logout_time else "Emp forgot to logout"

        total_logged_hours = (logout_time - time_entry.login_time).total_seconds() / 3600
        is_full_day = abs(total_logged_hours - TimeCalculator.STANDARD_WORK_HOURS) < 0.5

        details = {
            "total_logged_hours": total_logged_hours,
            "is_full_workday":    is_full_day,
            "login_time":         time_entry.login_time,
            "logout_time":        logout_time,
            "mandatory_breaks":   {},
            "bio_breaks":         {},
            "adjustments":        {},
            "overlap_handling":   {}
        }

        breaks, ov = TimeCalculator.handle_overlapping_breaks(time_entry.breaks)
        details["overlap_handling"] = ov

        total_break_min = 0
        b1_min = b2_min = 0
        bio_min = 0

        for br in breaks:
            dur = br.duration_minutes or 0
            total_break_min += dur

            if br.break_type == BreakType.BREAK1:
                b1_min = dur
                details["mandatory_breaks"]["break1"] = dur
            elif br.break_type == BreakType.BREAK2:
                b2_min = dur
                details["mandatory_breaks"]["break2"] = dur
            elif br.break_type == BreakType.BIO:
                bio_min += dur
                details["bio_breaks"][f"bio_break_{len(details['bio_breaks'])+1}"] = dur

        # full day case
        if is_full_day:
            base_hours  = TimeCalculator.STANDARD_WORK_HOURS
            penalty_min = 0
            bonus_min   = 0

            def _adj(actual, label):
                if actual > TimeCalculator.MANDATORY_BREAK_MINUTES:
                    excess = actual - TimeCalculator.MANDATORY_BREAK_MINUTES
                    details["adjustments"][f"{label}_excess"] = -excess
                    return -excess
                if 0 < actual < TimeCalculator.MANDATORY_BREAK_MINUTES:
                    unused = TimeCalculator.MANDATORY_BREAK_MINUTES - actual
                    details["adjustments"][f"{label}_unused"] = unused
                    return unused
                return 0

            bonus_min += _adj(b1_min, "break1")
            bonus_min += _adj(b2_min, "break2")

            if bio_min > TimeCalculator.MAX_BIO_BREAK_MINUTES:
                excess = bio_min - TimeCalculator.MAX_BIO_BREAK_MINUTES
                penalty_min += excess
                details["adjustments"]["bio_excess"] = -excess

            final_hours = max(0, min(
                base_hours,
                base_hours - (penalty_min / 60) + (bonus_min / 60)
            ))

        # partial day case
        else:
            productive = total_logged_hours - (total_break_min / 60)
            penalty_min = 0

            if b1_min > TimeCalculator.MANDATORY_BREAK_MINUTES:
                extra = b1_min - TimeCalculator.MANDATORY_BREAK_MINUTES
                penalty_min += extra
                details["adjustments"]["break1_excess_penalty"] = -extra

            if b2_min > TimeCalculator.MANDATORY_BREAK_MINUTES:
                extra = b2_min - TimeCalculator.MANDATORY_BREAK_MINUTES
                penalty_min += extra
                details["adjustments"]["break2_excess_penalty"] = -extra

            if bio_min > TimeCalculator.MAX_BIO_BREAK_MINUTES:
                extra = bio_min - TimeCalculator.MAX_BIO_BREAK_MINUTES
                penalty_min += extra
                details["adjustments"]["bio_excess_penalty"] = -extra

            final_hours = max(0, productive - (penalty_min / 60))

        details["total_break_minutes"] = total_break_min
        details["final_work_hours"]    = final_hours

        if penalty_min:
            scenario = "Emp exceeds break"
        if ov["has_overlaps"]:
            scenario += " with overlapping breaks"

        return final_hours, details, scenario
