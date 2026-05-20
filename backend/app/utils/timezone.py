from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


def to_kst_iso_system(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(KST).isoformat(timespec="seconds")
    return dt.astimezone(KST).isoformat(timespec="seconds")


def to_kst_iso_business(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST).isoformat(timespec="seconds")
    return dt.astimezone(KST).isoformat(timespec="seconds")


def parse_td_schedule_as_kst(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year=year, month=month, day=day, hour=hour, minute=minute, tzinfo=KST)


def epoch_seconds_from_kst_business_datetime(dt: datetime | None) -> int:
    if dt is None:
        raise ValueError("datetime 값이 없습니다.")
    if dt.tzinfo is None:
        return int(dt.replace(tzinfo=KST).timestamp())
    return int(dt.astimezone(KST).timestamp())
