"""Derive meal-only logging streaks (steps are not counted)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.core.database import Database
from app.models.streaks import UserStreak


def _utc_date(ts: datetime) -> date:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).date()


def _collect_meal_log_dates(db: Database, user_id: str) -> set[date]:
    dates: set[date] = set()
    for ts in db.images.list_meal_dates(user_id):
        if ts is not None:
            dates.add(_utc_date(ts))
    return dates


def _anchored_current_streak(dates: set[date], today: date) -> tuple[int, date | None]:
    if not dates:
        return 0, None
    max_d = max(dates)
    if max_d > today:
        max_d = today

    if (today - max_d).days > 1:
        return 0, max_d

    anchor = max_d
    cnt = 0
    d = anchor
    while d in dates:
        cnt += 1
        d -= timedelta(days=1)
    return cnt, anchor


def _longest_consecutive_run(dates: set[date]) -> int:
    if not dates:
        return 0
    sorted_dates = sorted(dates)
    best = 1
    cur = 1
    for i in range(1, len(sorted_dates)):
        prev, this = sorted_dates[i - 1], sorted_dates[i]
        if this == prev:
            continue
        if this == prev + timedelta(days=1):
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def sync_user_streak(db: Database, user_id: str) -> UserStreak:
    today = datetime.now(timezone.utc).date()
    dates = _collect_meal_log_dates(db, user_id)
    current, last_d = _anchored_current_streak(dates, today)
    longest = _longest_consecutive_run(dates)

    row = db.streaks.get(user_id)
    if row is None:
        row = UserStreak(
            user_id=user_id,
            current_streak=current,
            longest_streak=max(longest, current),
            last_logged_date=last_d,
        )
        db.streaks.save(row)
    else:
        row.current_streak = current
        row.longest_streak = max(row.longest_streak, longest, current)
        row.last_logged_date = last_d
        db.streaks.save(row)
    return row
