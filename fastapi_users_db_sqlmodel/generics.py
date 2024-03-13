from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import TIMESTAMP, TypeDecorator


def now_utc():
    return datetime.now(timezone.utc)


class TIMESTAMPAware(TypeDecorator):  # pragma: no cover
    """
    MySQL and SQLite will always return naive-Python datetimes.

    We store everything as UTC, but we want to have
    only offset-aware Python datetimes, even with MySQL and SQLite.
    """

    impl = TIMESTAMP
    cache_ok = True

    def process_result_value(self, value: Optional[datetime], dialect):
        if dialect.name != "postgresql":
            if value is not None:
                return value.replace(tzinfo=timezone.utc)
        return value
