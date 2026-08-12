from src.history import upsert_daily_history


def test_replaces_same_day_and_collapses_existing_duplicates():
    history = [
        {"date": "2026-08-10", "time": "08:00"},
        {"date": "2026-08-10", "time": "09:00"},
        {"date": "2026-08-11", "time": "08:00"},
    ]
    result = upsert_daily_history(history, {"date": "2026-08-11", "time": "12:00"})
    assert result == [
        {"date": "2026-08-10", "time": "09:00"},
        {"date": "2026-08-11", "time": "12:00"},
    ]


def test_keeps_only_latest_unique_dates():
    history = [{"date": f"2026-08-{day:02d}"} for day in range(1, 6)]
    result = upsert_daily_history(history, {"date": "2026-08-06"}, limit=3)
    assert [item["date"] for item in result] == ["2026-08-04", "2026-08-05", "2026-08-06"]
