"""
predictor.py
Standalone focus-time forecast engine.
Uses only Python stdlib — no circular imports.
"""

import datetime
import statistics
import json
from pathlib import Path

SESSIONS_FILE = Path("sessions.json")


def _load_sessions() -> list:
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _daily_minutes(days_back: int = 30) -> dict:
    sessions = _load_sessions()
    cutoff   = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    totals   = {}
    for s in sessions:
        if s.get("type") == "work" and s.get("date", "") >= cutoff:
            totals[s["date"]] = totals.get(s["date"], 0) + s.get("duration", 0)
    return totals


def _linear_trend(values: list) -> tuple:
    n = len(values)
    if n < 2:
        return 0.0, (values[0] if values else 0.0)
    xs     = list(range(n))
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(values)
    num    = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den    = sum((x - mean_x) ** 2 for x in xs)
    slope  = num / den if den else 0.0
    return slope, mean_y - slope * mean_x


def fmt_minutes(m: float) -> str:
    m = max(0, int(m))
    h, mn = divmod(m, 60)
    return f"{h}h{mn:02d}m" if h else f"{mn}m"


def get_level(minutes: float) -> str:
    if minutes >= 120: return "Excellent"
    if minutes >= 75:  return "Bon"
    if minutes >= 40:  return "Modéré"
    return "Faible"


def predict(days: int = 7) -> dict:
    """Return prediction dict for the next `days` days."""
    daily  = _daily_minutes(30)
    today  = datetime.date.today()

    history = []
    for i in range(29, -1, -1):
        d = (today - datetime.timedelta(days=i)).isoformat()
        history.append(daily.get(d, 0))

    slope, intercept = _linear_trend(history)
    recent_avg = statistics.mean(history[-7:]) if history else 0

    result = []
    for i in range(days):
        raw_pred = intercept + slope * (len(history) + i)
        blended  = max(0.0, 0.7 * recent_avg + 0.3 * raw_pred)
        date     = today + datetime.timedelta(days=i + 1)
        result.append({
            "day":       date.strftime("%a %d/%m"),
            "minutes":   round(blended),
            "formatted": fmt_minutes(blended),
            "level":     get_level(blended),
        })

    return {
        "predictions": result,
        "total_week":  fmt_minutes(sum(r["minutes"] for r in result)),
        "slope":       round(slope, 3),
    }