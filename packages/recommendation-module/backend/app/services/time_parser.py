from datetime import datetime, timedelta, timezone

def parse_time_window(question):
    q = question.lower()

    now = datetime.now(timezone.utc)

    if "last hour" in q:
        return now - timedelta(hours=1), now

    if "last 24 hours" in q:
        return now - timedelta(days=1), now

    if "today" in q:
        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        return start, now

    if "yesterday" in q:
        start = (
            now - timedelta(days=1)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        end = start + timedelta(days=1)

        return start, end

    return None