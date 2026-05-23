import re
from datetime import datetime, timedelta, timezone


SRI_LANKA_TZ = timezone(timedelta(hours=5, minutes=30))
UTC_TZ = timezone.utc


def parse_hour(text: str):
    pattern = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)"
    match = re.search(pattern, text.lower())

    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12

    if meridiem == "am" and hour == 12:
        hour = 0

    return hour, minute


def get_day_range_local(question: str):
    now_local = datetime.now(SRI_LANKA_TZ)
    q = question.lower()

    if "yesterday" in q:
        target_day = now_local.date() - timedelta(days=1)
    else:
        target_day = now_local.date()

    start_local = datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        0,
        0,
        0,
        tzinfo=SRI_LANKA_TZ,
    )

    end_local = start_local + timedelta(days=1)

    return start_local, end_local


def parse_time_window(question: str):
    q = question.lower()
    start_day_local, end_day_local = get_day_range_local(question)

    range_pattern = r"(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm))\s*(?:to|-|until)\s*(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm))"
    range_match = re.search(range_pattern, q)

    if range_match:
        first_time = parse_hour(range_match.group(1))
        second_time = parse_hour(range_match.group(2))

        if first_time and second_time:
            start_hour, start_minute = first_time
            end_hour, end_minute = second_time

            start_local = start_day_local.replace(hour=start_hour, minute=start_minute)
            end_local = start_day_local.replace(hour=end_hour, minute=end_minute)

            return {
                "start_utc": start_local.astimezone(UTC_TZ).isoformat(),
                "end_utc": end_local.astimezone(UTC_TZ).isoformat(),
                "start_local": start_local.isoformat(),
                "end_local": end_local.isoformat(),
                "timezone": "Asia/Colombo",
            }

    single_time = parse_hour(q)

    if single_time:
        hour, minute = single_time

        start_local = start_day_local.replace(hour=hour, minute=minute)
        end_local = start_local + timedelta(minutes=30)

        return {
            "start_utc": start_local.astimezone(UTC_TZ).isoformat(),
            "end_utc": end_local.astimezone(UTC_TZ).isoformat(),
            "start_local": start_local.isoformat(),
            "end_local": end_local.isoformat(),
            "timezone": "Asia/Colombo",
        }

    if "yesterday" in q:
        return {
            "start_utc": start_day_local.astimezone(UTC_TZ).isoformat(),
            "end_utc": end_day_local.astimezone(UTC_TZ).isoformat(),
            "start_local": start_day_local.isoformat(),
            "end_local": end_day_local.isoformat(),
            "timezone": "Asia/Colombo",
        }

    return None