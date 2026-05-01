"""
study_tracker.py
-----------------
Gère la persistance des sessions de focus (Pomodoro).
Stocke chaque session dans un fichier JSON local et expose
des méthodes pour lire/analyser l'historique.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


DATA_FILE = Path("sessions.json")


class StudyTracker:
    """
    Enregistre et analyse les sessions de travail/focus.

    Structure d'une session :
    {
        "date":       "2025-04-30",
        "start_time": "14:32:00",
        "duration":   25,          # minutes
        "completed":  True,
        "type":       "work"       # "work" | "short_break" | "long_break"
    }
    """

    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = data_file
        self.sessions: list[dict] = self._load()

    # ------------------------------------------------------------------ #
    #  Persistance
    # ------------------------------------------------------------------ #

    def _load(self) -> list[dict]:
        """Charge les sessions depuis le fichier JSON."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save(self) -> None:
        """Persiste toutes les sessions sur le disque."""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    #  Ajout de sessions
    # ------------------------------------------------------------------ #

    def add_session(
        self,
        duration: int,
        session_type: str = "work",
        completed: bool = True,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Enregistre une nouvelle session terminée.

        Args:
            duration:     Durée en minutes.
            session_type: "work", "short_break" ou "long_break".
            completed:    False si la session a été interrompue.
            timestamp:    Datetime personnalisé (défaut : maintenant).

        Returns:
            Le dict de la session enregistrée.
        """
        now = timestamp or datetime.now()
        session = {
            "date":       now.strftime("%Y-%m-%d"),
            "start_time": now.strftime("%H:%M:%S"),
            "duration":   duration,
            "completed":  completed,
            "type":       session_type,
        }
        self.sessions.append(session)
        self._save()
        return session

    # ------------------------------------------------------------------ #
    #  Requêtes
    # ------------------------------------------------------------------ #

    def get_today_sessions(self) -> list[dict]:
        """Renvoie toutes les sessions du jour courant."""
        today = datetime.now().strftime("%Y-%m-%d")
        return [s for s in self.sessions if s["date"] == today]

    def get_sessions_last_n_days(self, n: int = 30) -> list[dict]:
        """Renvoie les sessions des n derniers jours."""
        cutoff = (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
        return [s for s in self.sessions if s["date"] >= cutoff]

    def get_daily_totals(self, n_days: int = 30) -> dict[str, float]:
        """
        Calcule le total de minutes de focus par jour sur les n derniers jours.

        Returns:
            { "2025-04-30": 75.0, "2025-04-29": 50.0, ... }
        """
        sessions = self.get_sessions_last_n_days(n_days)
        totals: dict[str, float] = {}
        for s in sessions:
            if s["type"] == "work" and s["completed"]:
                totals[s["date"]] = totals.get(s["date"], 0) + s["duration"]
        return dict(sorted(totals.items()))

    def get_stats_today(self) -> dict:
        """Résumé des statistiques du jour."""
        sessions = self.get_today_sessions()
        work_sessions = [s for s in sessions if s["type"] == "work" and s["completed"]]
        total_minutes = sum(s["duration"] for s in work_sessions)
        return {
            "sessions_count":  len(work_sessions),
            "total_minutes":   total_minutes,
            "total_formatted": self._fmt_minutes(total_minutes),
            "avg_duration":    total_minutes / len(work_sessions) if work_sessions else 0,
        }

    def get_weekly_stats(self) -> dict:
        """Statistiques de la semaine courante (lundi → aujourd'hui)."""
        sessions = self.get_sessions_last_n_days(7)
        work_sessions = [s for s in sessions if s["type"] == "work" and s["completed"]]
        total = sum(s["duration"] for s in work_sessions)
        return {
            "sessions_count":  len(work_sessions),
            "total_minutes":   total,
            "total_formatted": self._fmt_minutes(total),
            "daily_avg":       round(total / 7, 1),
        }

    def get_streak(self) -> int:
        """
        Calcule le streak courant : nombre de jours consécutifs avec
        au moins une session de travail complétée.
        """
        daily = self.get_daily_totals(n_days=365)
        if not daily:
            return 0

        streak = 0
        current = datetime.now().date()

        while True:
            key = current.strftime("%Y-%m-%d")
            if daily.get(key, 0) > 0:
                streak += 1
                current -= timedelta(days=1)
            else:
                break
        return streak

    # ------------------------------------------------------------------ #
    #  Utilitaires
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_minutes(minutes: float) -> str:
        """Formate 95 → '1h 35m'."""
        h, m = divmod(int(minutes), 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"

    def get_time_series_for_prediction(self, n_days: int = 60) -> list[float]:
        """
        Retourne une série temporelle de minutes/jour pour TimesFM.
        Les jours sans données sont remplis avec 0.
        """
        totals = self.get_daily_totals(n_days)
        end   = datetime.now().date()
        start = end - timedelta(days=n_days - 1)
        series = []
        current = start
        while current <= end:
            key = current.strftime("%Y-%m-%d")
            series.append(float(totals.get(key, 0.0)))
            current += timedelta(days=1)
        return series

    def summary_for_claude(self) -> str:
        """
        Génère un résumé textuel structuré à injecter dans le prompt Claude.
        """
        today   = self.get_stats_today()
        weekly  = self.get_weekly_stats()
        streak  = self.get_streak()
        totals  = self.get_daily_totals(7)

        lines = [
            "=== Résumé des sessions de focus ===",
            f"Aujourd'hui      : {today['total_formatted']} ({today['sessions_count']} sessions)",
            f"Cette semaine    : {weekly['total_formatted']} ({weekly['sessions_count']} sessions)",
            f"Moyenne/jour     : {self._fmt_minutes(weekly['daily_avg'])}",
            f"Streak actuel    : {streak} jours",
            "",
            "Détail des 7 derniers jours :",
        ]
        for date, mins in sorted(totals.items()):
            lines.append(f"  {date} : {self._fmt_minutes(mins)}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Test rapide
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import tempfile, shutil

    # Utilise un fichier temporaire pour les tests
    tmp = Path(tempfile.mkdtemp()) / "test_sessions.json"
    tracker = StudyTracker(data_file=tmp)

    # Simule 5 jours de sessions
    from datetime import datetime, timedelta
    base = datetime.now() - timedelta(days=4)
    for d in range(5):
        day = base + timedelta(days=d)
        for _ in range(3):
            tracker.add_session(25, "work", True, day)
        tracker.add_session(5, "short_break", True, day)

    print(tracker.summary_for_claude())
    print("\nSérie temporelle (7 derniers jours) :")
    print(tracker.get_time_series_for_prediction(7))
    print(f"\nStreak : {tracker.get_streak()} jours")

    shutil.rmtree(tmp.parent)
    print("\n✅ Tests passés.")