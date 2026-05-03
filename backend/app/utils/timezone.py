"""
Timezone utilities for KAFIN.
All datetime operations should use MEZ (Central European Time).
"""
from datetime import datetime, timezone, timedelta
import pytz

# MEZ timezone (CET/CEST)
MEZ_TZ = pytz.timezone('Europe/Berlin')

def now_mez() -> datetime:
    """Get current time in MEZ (CET/CEST)."""
    return datetime.now(MEZ_TZ)

def utc_to_mez(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to MEZ."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(MEZ_TZ)

def to_mez(dt: datetime) -> datetime:
    """Convert any datetime to MEZ."""
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MEZ_TZ)

def mez_timestamp() -> str:
    """Get current MEZ timestamp as ISO string."""
    return now_mez().isoformat()

def mez_date_string() -> str:
    """Get current MEZ date as YYYY-MM-DD string."""
    return now_mez().strftime("%Y-%m-%d")

def mez_datetime_string() -> str:
    """Get current MEZ datetime as formatted string."""
    return now_mez().strftime("%Y-%m-%d %H:%M:%S")
