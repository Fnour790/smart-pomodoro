import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from datetime import datetime
import json
import os
import anthropic

WORK_MIN = 25
SHORT_BREAK_MIN = 5
LONG_BREAK_MIN = 15
SESSIONS_BEFORE_LONG = 4
DATA_FILE = "study_data.json"


class StudyTracker:
    def __init__(self):
        self.data_file = DATA_FILE
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return []

    def save_history(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def add_session(self, session_type, duration_min, subject="", notes=""):
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "type": session_type,
            "duration": duration_min,
            "subject": subject,
            "notes": notes
        }
        self.history.append(entry)
        self.save_history()

    def get_today_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        today_sessions = [s for s in self.history if s.get("date") == today]
        work_sessions = [s for s in today_sessions if s.get("type") == "work"]
        total_min = sum(s.get("duration", 0) for s in work_sessions)
        return {
            "sessions": len(work_sessions),
            "total_minutes": total_min,
            "subjects": list(set(s.get("subject", "") for s in work_sessions if s.get("subject")))
        }

    def get_history_summary(self, days=7):
        from datetime import timedelta
        summary = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_sessions = [s for s in self.history if s.get("date") == date and s.get("type") == "work"]
            total = sum(s.get("duration", 0) for s in day_sessions)
            summary.append({"date": date, "sessions": len(day_sessions), "minutes": total})
        return summary


class AICoach:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.conversation_history = []

    def get_advice(self, tracker: StudyTracker, user_message: str = "") -> str:
        stats = tracker.get_today_stats()
        history = tracker.get_history_summary(7)

        system_prompt = f"""Tu es un coach d'études bienveillant et motivant pour un assistant Pomodoro intelligent.
Tu aides l'utilisateur à optimiser ses sessions de travail.

Statistiques d'aujourd'hui :
- Sessions de travail : {stats['sessions']}
- Temps total : {stats['total_minutes']} minutes
- Sujets étudiés : {', '.join(stats['subjects']) if stats['subjects'] else 'Non spécifié'}

Historique des 7 derniers jours :
{json.dumps(history, ensure_ascii=False, indent=2)}

Réponds de façon concise (2-4 phrases max), en français, avec encouragement et conseils pratiques.
"""
        msg = user_message if user_message else "Donne-moi un conseil ou un encouragement basé sur mes statistiques."
        self.conversation_history.append({"role": "user", "content": msg})

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            system=system_prompt,
            messages=self.conversation_history
        )

        reply = response.content[0].text
        self.conversation_history.append({"role": "assistant", "content": reply})

        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return reply

    def suggest_next_action(self, sessions_done: int, tracker: StudyTracker) -> str:
        stats = tracker.get_today_stats()
        prompt = (
            f"L'utilisateur vient de terminer une session Pomodoro "
            f"({sessions_done} sessions aujourd'hui, {stats['total_minutes']} min au total). "
            f"Suggère brièvement ce qu'il devrait faire maintenant en 1-2 phrases."
        )
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text


class SmartPomodoroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🍅 Smart Pomodoro AI")
        self.root.geometry("520x700")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        self.tracker = StudyTracker()
        self.coach = AICoach()

        self.work_min = tk.IntVar(value=WORK_MIN)
        self.short_break_min = tk.IntVar(value=SHORT_BREAK_MIN)
        self.long_break_min = tk.IntVar(value=LONG_BREAK_MIN)

        self.sessions_done = 0
        self.current_mode = "work"
        self.is_running = False
        self.time_left = self.work_min.get() * 60
        self.subject = tk.StringVar(value="")

        self._build_ui()
        self._update_display()

    def _build_ui(self):
        BG    = "#1a1a2e"
        CARD  = "#16213e"
        ACCENT = "#e94560"
        TEXT  = "#eaeaea"
        MUTED = "#a0a0b0"

        # ── Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(20, 0))
        tk.Label(header, text="🍅 Smart Pomodoro AI", font=("Segoe UI", 18, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        self.stats_label = tk.Label(header, text="", font=("Segoe UI", 10),
                                    bg=BG, fg=MUTED)
        self.stats_label.pack(side="right")

        # ── Subject
        subj_frame = tk.Frame(self.root, bg=BG)
        subj_frame.pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(subj_frame, text="Sujet :", font=("Segoe UI", 10),
                 bg=BG, fg=MUTED).pack(side="left")
        tk.Entry(subj_frame, textvariable=self.subject, font=("Segoe UI", 11),
                 bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                 width=30).pack(side="left", padx=8)

        # ── Timer card
        timer_card = tk.Frame(self.root, bg=CARD)
        timer_card.pack(padx=20, pady=16, fill="x")

        self.mode_label = tk.Label(timer_card, text="TRAVAIL",
                                   font=("Segoe UI", 12, "bold"), bg=CARD, fg=ACCENT)
        self.mode_label.pack(pady=(16, 4))

        self.timer_label = tk.Label(timer_card, text="25:00",
                                    font=("Segoe UI", 64, "bold"), bg=CARD, fg=TEXT)
        self.timer_label.pack()

        style = ttk.Style()
        style.theme_use("default")
        style.configure("red.Horizontal.TProgressbar",
                        background=ACCENT, troughcolor=CARD, bordercolor=CARD)
        self.progress = ttk.Progressbar(timer_card, length=400, mode="determinate",
                                        style="red.Horizontal.TProgressbar")
        self.progress.pack(pady=10)

        self.session_label = tk.Label(timer_card, text="Session 1 / 4",
                                      font=("Segoe UI", 10), bg=CARD, fg=MUTED)
        self.session_label.pack(pady=(0, 16))

        # ── Controls
        ctrl = tk.Frame(self.root, bg=BG)
        ctrl.pack(pady=4)
        btn_cfg = dict(font=("Segoe UI", 12, "bold"), relief="flat",
                       bd=0, padx=20, pady=10, cursor="hand2")

        self.start_btn = tk.Button(ctrl, text="▶  Démarrer", bg=ACCENT, fg="white",
                                   command=self.toggle_timer, **btn_cfg)
        self.start_btn.grid(row=0, column=0, padx=6)
        tk.Button(ctrl, text="↺  Réinitialiser", bg=CARD, fg=TEXT,
                  command=self.reset_timer, **btn_cfg).grid(row=0, column=1, padx=6)
        tk.Button(ctrl, text="⏭  Sauter", bg=CARD, fg=MUTED,
                  command=self.skip_session, **btn_cfg).grid(row=0, column=2, padx=6)

        # ── Settings
        settings_card = tk.Frame(self.root, bg=CARD)
        settings_card.pack(padx=20, pady=10, fill="x")
        tk.Label(settings_card, text="Durées (minutes)", font=("Segoe UI", 10, "bold"),
                 bg=CARD, fg=MUTED).pack(pady=(8, 4))
        srow = tk.Frame(settings_card, bg=CARD)
        srow.pack()
        for label, var in [("Travail", self.work_min),
                            ("Pause courte", self.short_break_min),
                            ("Pause longue", self.long_break_min)]:
            f = tk.Frame(srow, bg=CARD)
            f.pack(side="left", padx=12)
            tk.Label(f, text=label, font=("Segoe UI", 9), bg=CARD, fg=MUTED).pack()
            tk.Spinbox(f, from_=1, to=60, textvariable=var, width=4,
                       bg=BG, fg=TEXT, buttonbackground=CARD, relief="flat",
                       font=("Segoe UI", 12), command=self.reset_timer).pack()
        tk.Frame(settings_card, bg=CARD, height=8).pack()

        # ── AI Coach
        ai_card = tk.Frame(self.root, bg=CARD)
        ai_card.pack(padx=20, pady=8, fill="both", expand=True)

        ai_header = tk.Frame(ai_card, bg=CARD)
        ai_header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(ai_header, text="🤖 Coach IA", font=("Segoe UI", 11, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        tk.Button(ai_header, text="Conseil ↗", font=("Segoe UI", 9),
                  bg=ACCENT, fg="white", relief="flat", padx=10, pady=4,
                  command=self._ask_coach_thread).pack(side="right")

        self.ai_text = tk.Text(ai_card, height=5, wrap="word",
                               font=("Segoe UI", 10), bg="#0f3460", fg=TEXT,
                               relief="flat", padx=10, pady=8, state="disabled")
        self.ai_text.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        chat_row = tk.Frame(ai_card, bg=CARD)
        chat_row.pack(fill="x", padx=12, pady=(0, 10))
        self.chat_entry = tk.Entry(chat_row, font=("Segoe UI", 10),
                                   bg="#0f3460", fg=TEXT, insertbackground=TEXT,
                                   relief="flat")
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=4)
        self.chat_entry.bind("<Return>", lambda e: self._ask_coach_thread())
        tk.Button(chat_row, text="Envoyer", font=("Segoe UI", 9),
                  bg=CARD, fg=TEXT, relief="flat", padx=10,
                  command=self._ask_coach_thread).pack(side="right")

        self._update_stats_label()

    # ── Timer ─────────────────────────────────────────────────────────────────
    def toggle_timer(self):
        if self.is_running:
            self.is_running = False
            self.start_btn.configure(text="▶  Reprendre")
        else:
            self.is_running = True
            self.start_btn.configure(text="⏸  Pause")
            threading.Thread(target=self._run_timer, daemon=True).start()

    def _run_timer(self):
        while self.time_left > 0 and self.is_running:
            time.sleep(1)
            self.time_left -= 1
            self.root.after(0, self._update_display)
        if self.time_left == 0:
            self.root.after(0, self._session_complete)

    def _session_complete(self):
        self.is_running = False
        self.start_btn.configure(text="▶  Démarrer")

        if self.current_mode == "work":
            self.sessions_done += 1
            self.tracker.add_session("work", self.work_min.get(), self.subject.get())
            messagebox.showinfo("🍅 Session terminée!",
                                f"Bravo! Session {self.sessions_done} complétée.\nPrenez une pause!")
            self._ask_suggestion_thread()
            if self.sessions_done % SESSIONS_BEFORE_LONG == 0:
                self.current_mode = "long_break"
                self.time_left = self.long_break_min.get() * 60
            else:
                self.current_mode = "short_break"
                self.time_left = self.short_break_min.get() * 60
        else:
            dur = (self.short_break_min.get()
                   if self.current_mode == "short_break"
                   else self.long_break_min.get())
            self.tracker.add_session(self.current_mode, dur)
            messagebox.showinfo("☕ Pause terminée!", "C'est reparti! Nouvelle session de travail.")
            self.current_mode = "work"
            self.time_left = self.work_min.get() * 60

        self._update_display()
        self._update_stats_label()

    def reset_timer(self):
        self.is_running = False
        self.current_mode = "work"
        self.time_left = self.work_min.get() * 60
        self.start_btn.configure(text="▶  Démarrer")
        self._update_display()

    def skip_session(self):
        self.is_running = False
        self.time_left = 0
        self._session_complete()

    def _update_display(self):
        mins, secs = divmod(self.time_left, 60)
        self.timer_label.configure(text=f"{mins:02d}:{secs:02d}")
        labels = {"work": "TRAVAIL", "short_break": "PAUSE COURTE", "long_break": "PAUSE LONGUE"}
        self.mode_label.configure(text=labels.get(self.current_mode, "TRAVAIL"))
        total = {
            "work": self.work_min.get(),
            "short_break": self.short_break_min.get(),
            "long_break": self.long_break_min.get()
        }[self.current_mode] * 60
        pct = ((total - self.time_left) / total) * 100 if total > 0 else 0
        self.progress["value"] = pct
        pos = (self.sessions_done % SESSIONS_BEFORE_LONG) + 1
        self.session_label.configure(
            text=f"Session {pos} / {SESSIONS_BEFORE_LONG}  •  Total aujourd'hui: {self.sessions_done}")

    def _update_stats_label(self):
        stats = self.tracker.get_today_stats()
        self.stats_label.configure(
            text=f"Aujourd'hui: {stats['sessions']} sessions · {stats['total_minutes']} min")

    # ── AI ────────────────────────────────────────────────────────────────────
    def _set_ai_text(self, text):
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("end", text)
        self.ai_text.configure(state="disabled")

    def _ask_coach_thread(self):
        user_msg = self.chat_entry.get().strip()
        self.chat_entry.delete(0, "end")
        self._set_ai_text("⏳ Le coach réfléchit...")
        threading.Thread(target=self._fetch_advice, args=(user_msg,), daemon=True).start()

    def _fetch_advice(self, user_msg=""):
        try:
            reply = self.coach.get_advice(self.tracker, user_msg)
        except Exception as exc:
            reply = f"Erreur IA: {exc}"
        # ✅ FIX: capturer 'reply' dans le paramètre par défaut du lambda
        self.root.after(0, lambda r=reply: self._set_ai_text(r))

    def _ask_suggestion_thread(self):
        threading.Thread(target=self._fetch_suggestion, daemon=True).start()

    def _fetch_suggestion(self):
        try:
            reply = self.coach.suggest_next_action(self.sessions_done, self.tracker)
        except Exception as exc:
            reply = f"Conseil IA indisponible: {exc}"
        # ✅ FIX: même correction
        self.root.after(0, lambda r=reply: self._set_ai_text(r))


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartPomodoroApp(root)
    root.mainloop()
