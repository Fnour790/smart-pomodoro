"""
promodo_ai.py
Core AI layer for FocusTrack.

  PomodoroPredictor  — forecast + AI assistant answers
  TodoManager        — CRUD wrapper for the to-do list
"""

import json
import datetime
import hashlib
from pathlib import Path

import predictor                        # standalone module, no circular import
from study_tracker import (
    TODOS_FILE,
    get_today_stats, get_week_stats, get_streak,
)


# ══════════════════════════════════════════════════════════════
#  PomodoroPredictor
# ══════════════════════════════════════════════════════════════

class PomodoroPredictor:
    """High-level predictor with formatting helpers and AI assistant."""

    def predict(self, days: int = 7) -> dict:
        return predictor.predict(days)

    def forecast_summary(self) -> str:
        result = self.predict(7)
        slope  = result["slope"]
        trend  = "↑ improving" if slope > 0 else ("↓ declining" if slope < -0.5 else "→ stable")
        return f"Next 7 days: ~{result['total_week']} predicted  |  Trend: {trend}"

    @staticmethod
    def _fmt(m: float) -> str:
        return predictor.fmt_minutes(m)

    def answer(self, question: str) -> str:
        """Rule-based AI assistant — no external LLM needed."""
        q      = question.lower()
        today_ = get_today_stats()
        streak = get_streak()
        week   = get_week_stats()
        pred   = self.predict(7)

        if any(w in q for w in ("predict", "forecast", "next week")):
            lines = [self.forecast_summary(), ""]
            for r in pred["predictions"]:
                lines.append(f"  {r['day']:12s}  {r['formatted']:6s}  [{r['level']}]")
            return "\n".join(lines)

        if any(w in q for w in ("streak", "consecutive")):
            return f"Your current streak is {streak} day{'s' if streak != 1 else ''}. Keep it up! 🔥"

        if any(w in q for w in ("today", "so far")):
            return (
                f"Today: {self._fmt(today_['minutes'])} focus "
                f"across {today_['sessions']} session{'s' if today_['sessions'] != 1 else ''}."
            )

        if any(w in q for w in ("week", "weekly")):
            return f"This week: {self._fmt(week)} of focus time."

        if any(w in q for w in ("tip", "advice", "improve")):
            tips = [
                "Front-load your hardest task in the first session of the day.",
                "Keep your phone in another room during work blocks.",
                "A 5-minute walk between sessions boosts retention significantly.",
                "Batch shallow tasks (email, admin) into one afternoon block.",
                "Consistent start times train your brain to enter focus faster.",
            ]
            idx = int(hashlib.md5(datetime.date.today().isoformat().encode()).hexdigest(), 16) % len(tips)
            return f"💡 Daily tip: {tips[idx]}"

        return (
            f"Today: {self._fmt(today_['minutes'])}  |  "
            f"Week: {self._fmt(week)}  |  "
            f"Streak: {streak}d  |  "
            f"Forecast: {pred['total_week']} next 7 days"
        )


# ══════════════════════════════════════════════════════════════
#  TodoManager
# ══════════════════════════════════════════════════════════════

class TodoManager:
    """CRUD manager for the to-do list, backed by a JSON file."""

    def __init__(self, data_file: Path = TODOS_FILE):
        self.data_file = data_file
        self.todos: list = self._load()

    def _load(self) -> list:
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _persist(self) -> None:
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.todos, f, indent=2, ensure_ascii=False)

    def add(self, text: str) -> dict:
        item = {"text": text, "done": False, "created": datetime.datetime.now().isoformat()}
        self.todos.append(item)
        self._persist()
        return item

    def toggle(self, index: int) -> bool:
        self.todos[index]["done"] = not self.todos[index]["done"]
        self._persist()
        return self.todos[index]["done"]

    def delete(self, index: int) -> None:
        self.todos.pop(index)
        self._persist()

    def pending(self) -> list:
        return [t for t in self.todos if not t["done"]]

    def completed(self) -> list:
        return [t for t in self.todos if t["done"]]

    def __repr__(self) -> str:
        return f"TodoManager({len(self.todos)} items, {len(self.pending())} pending)"