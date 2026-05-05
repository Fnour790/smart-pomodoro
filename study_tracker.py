"""
study_tracker.py
Handles persistence for sessions, todos, habits, and goals.
"""

import json
import datetime
from pathlib import Path

# ── File paths ──────────────────────────────────────────────
SESSIONS_FILE = Path("sessions.json")
HABITS_FILE   = Path("habits.json")
TODOS_FILE    = Path("todos.json")
GOALS_FILE    = Path("goals.json")


def _load(path: Path) -> list:
    """Load a JSON list from disk; return [] if missing or corrupt."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save(path: Path, data: list) -> None:
    """Persist a list to disk as formatted JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def today() -> str:
    return datetime.date.today().isoformat()


# ── Sessions ─────────────────────────────────────────────────
def get_sessions() -> list[dict]:
    return _load(SESSIONS_FILE)


def save_sessions(sessions: list[dict]) -> None:
    _save(SESSIONS_FILE, sessions)


def add_session(duration_minutes: int, session_type: str = "work") -> None:
    sessions = get_sessions()
    sessions.append(
        {
            "date":      today(),
            "start":     datetime.datetime.now().strftime("%H:%M:%S"),
            "duration":  duration_minutes,
            "type":      session_type,
            "completed": True,
        }
    )
    save_sessions(sessions)


def get_today_stats() -> dict:
    sessions = [s for s in get_sessions() if s.get("date") == today() and s.get("type") == "work"]
    total    = sum(s.get("duration", 0) for s in sessions)
    return {"minutes": total, "sessions": len(sessions)}


def get_week_stats() -> int:
    """Total focus minutes for the current ISO week."""
    week_start = (datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())).isoformat()
    return sum(
        s.get("duration", 0)
        for s in get_sessions()
        if s.get("date", "") >= week_start and s.get("type") == "work"
    )


def get_streak() -> int:
    """Number of consecutive days (ending today) with at least one session."""
    work_days = {s["date"] for s in get_sessions() if s.get("type") == "work"}
    streak, day = 0, datetime.date.today()
    while day.isoformat() in work_days:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


# ── Todos ─────────────────────────────────────────────────────
def get_todos() -> list[dict]:
    return _load(TODOS_FILE)


def save_todos(todos: list[dict]) -> None:
    _save(TODOS_FILE, todos)


def add_todo(text: str) -> None:
    todos = get_todos()
    todos.append({"text": text, "done": False, "created": datetime.datetime.now().isoformat()})
    save_todos(todos)


def toggle_todo(index: int) -> None:
    todos = get_todos()
    if 0 <= index < len(todos):
        todos[index]["done"] = not todos[index]["done"]
        save_todos(todos)


def delete_todo(index: int) -> None:
    todos = get_todos()
    if 0 <= index < len(todos):
        todos.pop(index)
        save_todos(todos)


# ── Habits ─────────────────────────────────────────────────────
def get_habits() -> list[dict]:
    return _load(HABITS_FILE)


def save_habits(habits: list[dict]) -> None:
    _save(HABITS_FILE, habits)


def add_habit(name: str) -> None:
    habits = get_habits()
    habits.append({"name": name, "streak": 0, "last_done": None})
    save_habits(habits)


def check_habit(index: int) -> None:
    habits = get_habits()
    if 0 <= index < len(habits):
        t = today()
        if habits[index].get("last_done") != t:
            habits[index]["streak"]    += 1
            habits[index]["last_done"]  = t
            save_habits(habits)


def delete_habit(index: int) -> None:
    habits = get_habits()
    if 0 <= index < len(habits):
        habits.pop(index)
        save_habits(habits)


# ── Goals ─────────────────────────────────────────────────────
def get_goals() -> list[dict]:
    return _load(GOALS_FILE)


def save_goals(goals: list[dict]) -> None:
    _save(GOALS_FILE, goals)


def add_goal(name: str, target: int, unit: str = "units") -> None:
    goals = get_goals()
    goals.append({"name": name, "target": target, "current": 0, "unit": unit, "created": today()})
    save_goals(goals)


def progress_goal(index: int, amount: int = 1) -> None:
    goals = get_goals()
    if 0 <= index < len(goals):
        goals[index]["current"] = min(goals[index]["current"] + amount, goals[index]["target"])
        save_goals(goals)


def delete_goal(index: int) -> None:
    goals = get_goals()
    if 0 <= index < len(goals):
        goals.pop(index)
        save_goals(goals)