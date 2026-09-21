from datetime import date, datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))  # Việt Nam không có DST nên dùng offset cố định


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today_vn() -> date:
    return datetime.now(VN_TZ).date()
