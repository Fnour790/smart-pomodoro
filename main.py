"""
main.py
FocusTrack — Smart Pomodoro AI with TimeFM Predictions
Redesigned to match the HTML UI (focustrack_pomodoro_ui.html)
"""

import tkinter as tk
from tkinter import ttk
import datetime
import json
import random
from pathlib import Path

from promodo_ai import PomodoroPredictor, TodoManager
from study_tracker import (
    add_session, get_today_stats, get_week_stats, get_streak,
    get_habits, check_habit, delete_habit, add_habit,
    get_goals, add_goal, progress_goal, delete_goal,
    get_sessions
)

# ── Config ────────────────────────────────────────────────────
_cfg_path = Path("pomodoro_config.json")
CFG = json.loads(_cfg_path.read_text()) if _cfg_path.exists() else {
    "work_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "sessions_before_long_break": 4,
}

def save_cfg():
    with open("pomodoro_config.json", "w") as f:
        json.dump(CFG, f, indent=2)

# ── Palette (matches CSS variables) ──────────────────────────
BG      = "#080b10"
SURF    = "#0e1118"
SURF2   = "#141820"
SURF3   = "#1a2030"
BORDER  = "#1f2535"
ACCENT  = "#ff6b35"
ACCENT2 = "#3d8bff"
ACCENT3 = "#36d9a0"
ACCENT4 = "#c87fff"
TEXT    = "#e8eaf2"
MUTED   = "#4a5268"
MUTED2  = "#6b7591"
YELLOW  = "#f0b429"
RED     = "#e04545"
GREEN   = "#36d9a0"

MONO    = ("Courier New", 10)
MONO_SM = ("Courier New", 9)
MONO_LG = ("Courier New", 13, "bold")
MONO_XL = ("Courier New", 60, "bold")
SANS    = ("Segoe UI", 10)

MODE_COLOR = {"work": ACCENT, "short": GREEN, "long": ACCENT4}
MODE_LABEL = {"work": "DEEP FOCUS", "short": "SHORT BREAK", "long": "LONG BREAK"}


# ── Timer State ───────────────────────────────────────────────
class TimerState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.running      = False
        self.seconds_left = CFG["work_minutes"] * 60
        self.total_seconds = CFG["work_minutes"] * 60
        self.mode         = "work"
        self.session_num  = 1
        self.completed    = 0

    def toggle(self):
        self.running = not self.running

    def skip(self):
        self.running = False
        self._next_mode()

    def tick(self):
        if self.running:
            if self.seconds_left > 0:
                self.seconds_left -= 1
            else:
                self._next_mode()

    def _next_mode(self):
        if self.mode == "work":
            self.completed += 1
            add_session(CFG["work_minutes"])
            if self.completed % CFG["sessions_before_long_break"] == 0:
                self.mode = "long"
                self.seconds_left = self.total_seconds = CFG["long_break_minutes"] * 60
            else:
                self.mode = "short"
                self.seconds_left = self.total_seconds = CFG["short_break_minutes"] * 60
            self.session_num = min(self.session_num + 1, CFG["sessions_before_long_break"])
        else:
            self.mode = "work"
            self.seconds_left = self.total_seconds = CFG["work_minutes"] * 60

    @property
    def display(self):
        m, s = divmod(self.seconds_left, 60)
        return f"{m:02d}:{s:02d}"

    @property
    def progress(self):
        return 1 - self.seconds_left / max(self.total_seconds, 1)


# ── App ───────────────────────────────────────────────────────
class FocusTrackApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FocusTrack — Smart Pomodoro AI")
        self.root.configure(bg=BG)
        self.root.geometry("1200x720")
        self.root.minsize(900, 600)

        self.timer = TimerState()
        self.ai    = PomodoroPredictor()
        self.todos = TodoManager()

        self._build_ui()
        self._tick()
        self._refresh_all()

    # ── Layout ────────────────────────────────────────────────
    def _build_ui(self):
        app = tk.Frame(self.root, bg=BG)
        app.pack(fill="both", expand=True)

        # Two-column grid: 280px left | flex right
        left = tk.Frame(app, bg=SURF, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        right = tk.Frame(app, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_left(left)
        self._build_right(right)

    # ── LEFT PANEL ────────────────────────────────────────────
    def _build_left(self, parent):
        pad = dict(padx=20)

        # Brand
        brand = tk.Frame(parent, bg=SURF)
        brand.pack(fill="x", pady=(22, 0), **pad)
        icon_box = tk.Label(brand, text="🍅", bg=ACCENT, fg="white",
                            font=("Segoe UI", 14), width=3, relief="flat")
        icon_box.pack(side="left")
        tk.Label(brand, text="  FOCUS TRACK", bg=SURF, fg=ACCENT,
                 font=("Courier New", 13, "bold")).pack(side="left")

        # Mode badge
        self.mode_badge = tk.Label(parent, text="● DEEP FOCUS", bg=SURF3,
                                   fg=MUTED2, font=MONO_SM, relief="flat",
                                   padx=12, pady=5)
        self.mode_badge.pack(pady=(22, 0))

        # Timer display
        self.timer_label = tk.Label(parent, text="25:00", font=MONO_XL,
                                    bg=SURF, fg=ACCENT)
        self.timer_label.pack(pady=(10, 0))

        # Session info
        self.session_label = tk.Label(parent, text="Session 1 / 4",
                                      bg=SURF, fg=MUTED2, font=MONO_SM)
        self.session_label.pack(pady=(4, 8))

        # Progress bar
        self.prog_canvas = tk.Canvas(parent, height=5, bg=SURF3,
                                     highlightthickness=0)
        self.prog_canvas.pack(fill="x", padx=20, pady=(0, 16))
        self.prog_bar = self.prog_canvas.create_rectangle(
            0, 0, 0, 5, fill=ACCENT, outline="")

        # Controls
        ctrl = tk.Frame(parent, bg=SURF)
        ctrl.pack(fill="x", **pad, pady=(0, 18))

        self.start_btn = tk.Button(
            ctrl, text="▶ START", font=MONO_LG,
            bg=ACCENT, fg="white", activebackground="#ff8055",
            relief="flat", cursor="hand2",
            command=self._toggle_timer)
        self.start_btn.pack(side="left", fill="x", expand=True, ipady=8)

        tk.Button(ctrl, text="⏭", font=MONO_LG, bg=SURF3, fg=MUTED2,
                  activebackground=BORDER, relief="flat", cursor="hand2",
                  command=self._skip, width=3).pack(side="left", padx=(6, 0), ipady=8)

        tk.Button(ctrl, text="↺", font=MONO_LG, bg=SURF3, fg=MUTED2,
                  activebackground=BORDER, relief="flat", cursor="hand2",
                  command=self._reset, width=3).pack(side="left", padx=(6, 0), ipady=8)

        # Settings box
        box = tk.Frame(parent, bg=SURF2, relief="flat", bd=0)
        box.pack(fill="x", **pad, pady=(0, 20))

        tk.Label(box, text="⚙  CUSTOM TIMERS", bg=SURF2, fg=MUTED2,
                 font=("Courier New", 9), pady=10).pack(anchor="w", padx=12)

        self.work_var     = tk.IntVar(value=CFG["work_minutes"])
        self.short_var    = tk.IntVar(value=CFG["short_break_minutes"])
        self.long_var     = tk.IntVar(value=CFG["long_break_minutes"])
        self.sessions_var = tk.IntVar(value=CFG["sessions_before_long_break"])

        rows = [
            ("Work (min)",          self.work_var,     5,  1,  120),
            ("Short break",         self.short_var,    1,  1,   30),
            ("Long break",          self.long_var,     5,  1,   60),
            ("Sessions → long",     self.sessions_var, 1,  1,    8),
        ]
        for label, var, step, lo, hi in rows:
            self._setting_row(box, label, var, step, lo, hi)

    def _setting_row(self, parent, label, var, step, lo, hi):
        row = tk.Frame(parent, bg=SURF2)
        row.pack(fill="x", padx=12, pady=4)

        tk.Label(row, text=label, bg=SURF2, fg=MUTED2,
                 font=MONO_SM).pack(side="left")

        val_lbl = tk.Label(row, textvariable=var, bg=SURF2,
                           fg=TEXT, font=MONO, width=3)
        val_lbl.pack(side="right")

        tk.Button(row, text="+", bg=SURF3, fg=MUTED2, relief="flat",
                  cursor="hand2", font=MONO_SM, width=2,
                  command=lambda v=var, s=step, h=hi: self._adj(v, s, h)).pack(
                  side="right", padx=(4, 2))
        tk.Button(row, text="−", bg=SURF3, fg=MUTED2, relief="flat",
                  cursor="hand2", font=MONO_SM, width=2,
                  command=lambda v=var, s=step, l=lo: self._adj(v, -s, 999, l)).pack(
                  side="right", padx=(0, 2))

    def _adj(self, var, delta, hi=999, lo=1):
        var.set(max(lo, min(hi, var.get() + delta)))
        CFG["work_minutes"]              = self.work_var.get()
        CFG["short_break_minutes"]       = self.short_var.get()
        CFG["long_break_minutes"]        = self.long_var.get()
        CFG["sessions_before_long_break"] = self.sessions_var.get()
        save_cfg()
        if not self.timer.running:
            self._reset()

    # ── RIGHT PANEL ───────────────────────────────────────────
    def _build_right(self, parent):
        # Tab bar
        tab_bar = tk.Frame(parent, bg=SURF, height=44)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self.tab_btns = {}
        self.tab_frames = {}
        tabs = [
            ("stats",  "📊 Stats"),
            ("charts", "📈 Charts"),
            ("ai",     "🤖 AI"),
            ("todo",   "✅ To-do"),
            ("habits", "🔥 Habits"),
            ("goals",  "🎯 Goals"),
        ]
        for key, label in tabs:
            btn = tk.Button(tab_bar, text=label, font=MONO_SM,
                            bg=SURF2, fg=MUTED2, relief="flat",
                            cursor="hand2", padx=14, pady=8,
                            command=lambda k=key: self._switch_tab(k))
            btn.pack(side="left")
            self.tab_btns[key] = btn

        # Content area
        content = tk.Frame(parent, bg=BG)
        content.pack(fill="both", expand=True)

        for key, _ in tabs:
            frame = tk.Frame(content, bg=BG)
            frame.place(relwidth=1, relheight=1)
            self.tab_frames[key] = frame

        self._build_stats_tab(self.tab_frames["stats"])
        self._build_charts_tab(self.tab_frames["charts"])
        self._build_ai_tab(self.tab_frames["ai"])
        self._build_todo_tab(self.tab_frames["todo"])
        self._build_habits_tab(self.tab_frames["habits"])
        self._build_goals_tab(self.tab_frames["goals"])

        self._switch_tab("stats")

    def _switch_tab(self, active):
        for key, frame in self.tab_frames.items():
            frame.lower()
            self.tab_btns[key].config(bg=SURF2, fg=MUTED2)
        self.tab_frames[active].lift()
        self.tab_btns[active].config(bg=SURF3, fg=ACCENT2)

        if active in ("stats", "charts"):
            self._draw_bars()
        if active == "ai":
            self._draw_predictions()

    # ── STATS TAB ─────────────────────────────────────────────
    def _build_stats_tab(self, parent):
        pad = dict(padx=20, pady=10)

        # 2×2 stat cards
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x", **pad)

        self.stat_today  = self._stat_card(grid, "TODAY'S FOCUS",  "0 min",   "0 sessions completed", ACCENT)
        self.stat_week   = self._stat_card(grid, "THIS WEEK",       "0 min",   "total focus time",      ACCENT2)
        self.stat_all    = self._stat_card(grid, "ALL TIME",        "0h 0m",   "0 total sessions",      ACCENT3)
        self.stat_streak = self._stat_card(grid, "STREAK",          "0 days",  "in a row — keep it up!", ACCENT4)

        for i, card in enumerate([self.stat_today, self.stat_week,
                                   self.stat_all,  self.stat_streak]):
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=5, pady=5)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Bar chart
        tk.Label(parent, text="LAST 7 DAYS", bg=BG, fg=MUTED2,
                 font=("Courier New", 9), anchor="w").pack(
                 fill="x", padx=20, pady=(10, 4))

        self.stats_chart = tk.Canvas(parent, height=160, bg=BG,
                                     highlightthickness=0)
        self.stats_chart.pack(fill="x", padx=20)

        # Tips box
        tip = tk.Frame(parent, bg=SURF, relief="flat")
        tip.pack(fill="x", padx=20, pady=14)
        tk.Label(tip, text="💡 FOCUS TIPS", bg=SURF, fg=ACCENT3,
                 font=("Courier New", 9), pady=8).pack(anchor="w", padx=12)
        self.tip_label = tk.Label(
            tip,
            text=f"Take a break every {CFG['sessions_before_long_break']} sessions  ·  "
                 "Stay hydrated  ·  Remove distractions for deep work",
            bg=SURF, fg=MUTED2, font=SANS, wraplength=700, justify="left")
        self.tip_label.pack(anchor="w", padx=12, pady=(0, 10))

    def _stat_card(self, parent, label, value, sub, color):
        card = tk.Frame(parent, bg=SURF, relief="flat")
        tk.Label(card, text=label, bg=SURF, fg=MUTED2,
                 font=("Courier New", 9), anchor="w").pack(
                 fill="x", padx=14, pady=(14, 4))
        val_lbl = tk.Label(card, text=value, bg=SURF, fg=color,
                           font=("Courier New", 22, "bold"), anchor="w")
        val_lbl.pack(fill="x", padx=14)
        tk.Label(card, text=sub, bg=SURF, fg=MUTED2,
                 font=MONO_SM, anchor="w").pack(fill="x", padx=14, pady=(2, 12))
        card._val = val_lbl
        return card

    # ── CHARTS TAB ────────────────────────────────────────────
    def _build_charts_tab(self, parent):
        tk.Label(parent, text="WEEKLY FOCUS TIME (MINUTES)", bg=BG, fg=MUTED2,
                 font=("Courier New", 9), anchor="w").pack(
                 fill="x", padx=20, pady=(16, 4))
        self.charts_chart = tk.Canvas(parent, height=220, bg=BG,
                                      highlightthickness=0)
        self.charts_chart.pack(fill="x", padx=20)

    # ── AI TAB ────────────────────────────────────────────────
    def _build_ai_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 8))

        self.ai_entry = tk.Entry(top, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                  font=MONO, relief="flat")
        self.ai_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.ai_entry.insert(0, "predict my week")
        self.ai_entry.bind("<Return>", lambda _: self._ask_ai())

        tk.Button(top, text="Ask ↗", bg=ACCENT, fg="white", font=MONO_LG,
                  relief="flat", cursor="hand2", padx=16,
                  command=self._ask_ai).pack(side="left", ipady=6)

        self.ai_response = tk.Text(parent, bg=SURF, fg=ACCENT4, font=MONO,
                                    relief="flat", wrap="word", height=9,
                                    padx=16, pady=14)
        self.ai_response.pack(fill="x", padx=20)
        self.ai_response.insert("1.0", "🤖 AI insights will appear here after you click Ask...")
        self.ai_response.config(state="disabled")

        tk.Label(parent, text="7-DAY FOCUS PREDICTION", bg=BG, fg=MUTED2,
                 font=("Courier New", 9), anchor="w").pack(
                 fill="x", padx=20, pady=(14, 4))
        self.pred_canvas = tk.Canvas(parent, height=130, bg=BG,
                                      highlightthickness=0)
        self.pred_canvas.pack(fill="x", padx=20)

    # ── TODO TAB ──────────────────────────────────────────────
    def _build_todo_tab(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=20, pady=16)

        self.todo_entry = tk.Entry(row, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                    font=MONO, relief="flat")
        self.todo_entry.pack(side="left", fill="x", expand=True, ipady=8,
                              padx=(0, 8))
        self.todo_entry.insert(0, "")
        self.todo_entry.bind("<Return>", lambda _: self._add_todo())

        tk.Button(row, text="+ Add", bg=ACCENT2, fg="white", font=SANS,
                  relief="flat", cursor="hand2",
                  command=self._add_todo).pack(side="left", ipady=6, padx=2)

        self.todo_list_frame = _ScrollFrame(parent, bg=BG)
        self.todo_list_frame.pack(fill="both", expand=True, padx=20)

    # ── HABITS TAB ────────────────────────────────────────────
    def _build_habits_tab(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=20, pady=16)

        self.habit_entry = tk.Entry(row, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                     font=MONO, relief="flat")
        self.habit_entry.pack(side="left", fill="x", expand=True, ipady=8,
                               padx=(0, 8))
        self.habit_entry.bind("<Return>", lambda _: self._add_habit())

        tk.Button(row, text="+ Add", bg=ACCENT3, fg="#000", font=SANS,
                  relief="flat", cursor="hand2",
                  command=self._add_habit).pack(side="left", ipady=6, padx=2)

        self.habit_list_frame = _ScrollFrame(parent, bg=BG)
        self.habit_list_frame.pack(fill="both", expand=True, padx=20)

    # ── GOALS TAB ─────────────────────────────────────────────
    def _build_goals_tab(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=20, pady=16)

        self.goal_name_entry = tk.Entry(row, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                         font=MONO, relief="flat")
        self.goal_name_entry.pack(side="left", fill="x", expand=True, ipady=8,
                                   padx=(0, 6))
        self.goal_name_entry.insert(0, "Goal name")

        self.goal_target_entry = tk.Entry(row, bg=SURF, fg=TEXT, insertbackground=TEXT,
                                           font=MONO, relief="flat", width=8)
        self.goal_target_entry.pack(side="left", ipady=8, padx=(0, 6))
        self.goal_target_entry.insert(0, "100")

        tk.Button(row, text="+ Add", bg=ACCENT4, fg="white", font=SANS,
                  relief="flat", cursor="hand2",
                  command=self._add_goal).pack(side="left", ipady=6)

        self.goal_list_frame = _ScrollFrame(parent, bg=BG)
        self.goal_list_frame.pack(fill="both", expand=True, padx=20)

    # ── TIMER LOGIC ───────────────────────────────────────────
    def _toggle_timer(self):
        self.timer.toggle()
        self.start_btn.config(
            text="⏸ PAUSE" if self.timer.running else "▶ START")

    def _skip(self):
        self.timer.skip()

    def _reset(self):
        self.timer.reset()
        self.start_btn.config(text="▶ START")

    def _tick(self):
        self.timer.tick()
        self._update_timer_display()
        self.root.after(1000, self._tick)

    def _update_timer_display(self):
        color = MODE_COLOR[self.timer.mode]

        self.timer_label.config(text=self.timer.display, fg=color)
        self.mode_badge.config(
            text=f"●  {MODE_LABEL[self.timer.mode]}",
            fg=color)
        self.session_label.config(
            text=f"Session {self.timer.session_num} / "
                 f"{CFG['sessions_before_long_break']}")

        # Progress bar
        self.prog_canvas.update_idletasks()
        w = self.prog_canvas.winfo_width()
        fill_w = int(w * self.timer.progress)
        self.prog_canvas.coords(self.prog_bar, 0, 0, fill_w, 5)
        self.prog_canvas.itemconfig(self.prog_bar, fill=color)

    # ── CHARTS ────────────────────────────────────────────────
    def _bar_data_7days(self):
        sessions = get_sessions()
        today = datetime.date.today()
        day_map = {}
        for i in range(7):
            d = today - datetime.timedelta(days=6 - i)
            day_map[d.isoformat()] = 0
        for s in sessions:
            if s.get("type") == "work" and s["date"] in day_map:
                day_map[s["date"]] += s.get("duration", 0)
        result = []
        for iso, mins in day_map.items():
            result.append({
                "day": datetime.date.fromisoformat(iso).strftime("%a"),
                "min": mins
            })
        return result

    def _draw_bars_on(self, canvas, data, height=None):
        canvas.delete("all")
        canvas.update_idletasks()
        W = canvas.winfo_width() or 700
        H = height or (canvas.winfo_height() or 160)
        n = len(data)
        if not n:
            canvas.create_text(W // 2, H // 2,
                                text="No data yet — complete some sessions!",
                                fill=MUTED2, font=MONO)
            return
        gap = 8
        bar_w = (W - gap * (n + 1)) // n
        max_m = max(d["min"] for d in data) or 60
        base_y = H - 28

        # Baseline
        canvas.create_line(0, base_y, W, base_y, fill=BORDER)

        for i, d in enumerate(data):
            x = gap + i * (bar_w + gap)
            bar_h = max(4, int((d["min"] / max_m) * (base_y - 24)))
            y0 = base_y - bar_h
            color = ACCENT if i == n - 1 else ACCENT2
            canvas.create_rectangle(x, y0, x + bar_w, base_y,
                                     fill=color, outline="")
            canvas.create_text(x + bar_w // 2, y0 - 10,
                                text=str(d["min"]),
                                fill=MUTED2, font=MONO_SM)
            canvas.create_text(x + bar_w // 2, base_y + 10,
                                text=d["day"],
                                fill=MUTED2, font=MONO_SM)

    def _draw_bars(self):
        data = self._bar_data_7days()
        self._draw_bars_on(self.stats_chart,  data, height=140)
        self._draw_bars_on(self.charts_chart, data, height=200)

    def _draw_predictions(self):
        self.pred_canvas.delete("all")
        self.pred_canvas.update_idletasks()
        try:
            pred = self.ai.predict(7)["predictions"]
        except Exception:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            pred = [{"day": d, "minutes": random.randint(20, 90),
                     "formatted": f"{random.randint(20,90)}m"} for d in days]

        W = self.pred_canvas.winfo_width() or 700
        H = self.pred_canvas.winfo_height() or 120
        n = len(pred)
        gap = 6
        bar_w = (W - gap * (n + 1)) // n
        max_m = max(p["minutes"] for p in pred) or 60
        base_y = H - 22

        self.pred_canvas.create_line(0, base_y, W, base_y, fill=BORDER)

        for i, p in enumerate(pred):
            x = gap + i * (bar_w + gap)
            bar_h = max(4, int((p["minutes"] / max_m) * (base_y - 18)))
            y0 = base_y - bar_h
            color = ACCENT3 if i < 5 else ACCENT4
            self.pred_canvas.create_rectangle(x, y0, x + bar_w, base_y,
                                               fill=color, outline="")
            self.pred_canvas.create_text(x + bar_w // 2, y0 - 9,
                                          text=p.get("formatted", f"{p['minutes']}m"),
                                          fill=MUTED2, font=MONO_SM)
            self.pred_canvas.create_text(x + bar_w // 2, base_y + 10,
                                          text=p["day"][:3],
                                          fill=MUTED2, font=MONO_SM)

    # ── AI ────────────────────────────────────────────────────
    def _ask_ai(self):
        q = self.ai_entry.get().strip() or "predict my week"
        self.ai_response.config(state="normal")
        self.ai_response.delete("1.0", "end")
        self.ai_response.insert("1.0", "🤔 Thinking...")
        self.ai_response.config(state="disabled")
        self.root.update()

        answer = self.ai.answer(q)
        self.ai_response.config(state="normal")
        self.ai_response.delete("1.0", "end")
        self.ai_response.insert("1.0", answer)
        self.ai_response.config(state="disabled")
        self._draw_predictions()

    # ── TODO ──────────────────────────────────────────────────
    def _add_todo(self):
        text = self.todo_entry.get().strip()
        if text:
            self.todos.add(text)
            self.todo_entry.delete(0, "end")
            self._render_todos()

    def _render_todos(self):
        f = self.todo_list_frame.inner
        for w in f.winfo_children():
            w.destroy()
        if not self.todos.todos:
            tk.Label(f, text="No tasks yet — add one above",
                     bg=BG, fg=MUTED, font=MONO).pack(pady=30)
            return
        for i, t in enumerate(self.todos.todos):
            self._todo_row(f, i, t)

    def _todo_row(self, parent, i, t):
        row = tk.Frame(parent, bg=SURF, relief="flat")
        row.pack(fill="x", pady=3)

        check = tk.Button(
            row,
            text="✓" if t["done"] else "",
            bg=GREEN if t["done"] else SURF3,
            fg="#000" if t["done"] else MUTED2,
            relief="flat", cursor="hand2", width=3,
            command=lambda idx=i: self._toggle_todo(idx))
        check.pack(side="left", padx=10, pady=8)

        color = MUTED if t["done"] else TEXT
        font  = (MONO[0], MONO[1], "overstrike") if t["done"] else MONO
        tk.Label(row, text=t["text"], bg=SURF, fg=color,
                 font=font).pack(side="left", fill="x", expand=True)

        tk.Button(row, text="✕", bg=SURF, fg=MUTED, relief="flat",
                  cursor="hand2",
                  command=lambda idx=i: self._delete_todo(idx)).pack(
                  side="right", padx=10)

    def _toggle_todo(self, i):
        self.todos.toggle(i)
        self._render_todos()

    def _delete_todo(self, i):
        self.todos.delete(i)
        self._render_todos()

    # ── HABITS ────────────────────────────────────────────────
    def _add_habit(self):
        name = self.habit_entry.get().strip()
        if name:
            add_habit(name)
            self.habit_entry.delete(0, "end")
            self._render_habits()

    def _render_habits(self):
        f = self.habit_list_frame.inner
        for w in f.winfo_children():
            w.destroy()
        habits = get_habits()
        if not habits:
            tk.Label(f, text="No habits yet — start building one",
                     bg=BG, fg=MUTED, font=MONO).pack(pady=30)
            return
        today_str = datetime.date.today().isoformat()
        for i, h in enumerate(habits):
            self._habit_row(f, i, h, today_str)

    def _habit_row(self, parent, i, h, today_str):
        row = tk.Frame(parent, bg=SURF, relief="flat")
        row.pack(fill="x", pady=3)

        done = h.get("last_done") == today_str
        fire = tk.Button(
            row,
            text="✅" if done else "🔥",
            bg=SURF3, relief="flat", cursor="hand2",
            font=("Segoe UI", 13), width=3,
            command=lambda idx=i: self._check_habit(idx))
        fire.pack(side="left", padx=8, pady=8)

        tk.Label(row, text=h["name"], bg=SURF, fg=TEXT,
                 font=SANS).pack(side="left", fill="x", expand=True)

        tk.Label(row, text=f"🔥 {h['streak']} days",
                 bg=SURF3, fg=YELLOW, font=MONO_SM,
                 relief="flat", padx=8, pady=3).pack(side="right", padx=6)

        tk.Button(row, text="✕", bg=SURF, fg=MUTED, relief="flat",
                  cursor="hand2",
                  command=lambda idx=i: self._delete_habit(idx)).pack(
                  side="right", padx=6)

    def _check_habit(self, i):
        check_habit(i)
        self._render_habits()

    def _delete_habit(self, i):
        delete_habit(i)
        self._render_habits()

    # ── GOALS ─────────────────────────────────────────────────
    def _add_goal(self):
        name = self.goal_name_entry.get().strip()
        if name and name != "Goal name":
            try:
                target = int(self.goal_target_entry.get())
                add_goal(name, target)
                self.goal_name_entry.delete(0, "end")
                self.goal_name_entry.insert(0, "Goal name")
                self.goal_target_entry.delete(0, "end")
                self.goal_target_entry.insert(0, "100")
                self._render_goals()
            except ValueError:
                pass

    def _render_goals(self):
        f = self.goal_list_frame.inner
        for w in f.winfo_children():
            w.destroy()
        goals = get_goals()
        if not goals:
            tk.Label(f, text="No goals yet — set one to get started",
                     bg=BG, fg=MUTED, font=MONO).pack(pady=30)
            return
        for i, g in enumerate(goals):
            self._goal_card(f, i, g)

    def _goal_card(self, parent, i, g):
        card = tk.Frame(parent, bg=SURF, relief="flat")
        card.pack(fill="x", pady=4)

        pct = int((g["current"] / g["target"]) * 100) if g["target"] else 0

        # Header
        hdr = tk.Frame(card, bg=SURF)
        hdr.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(hdr, text=g["name"], bg=SURF, fg=TEXT,
                 font=SANS).pack(side="left")
        tk.Label(hdr, text=f"{pct}%", bg=SURF, fg=ACCENT2,
                 font=MONO).pack(side="right")

        # Progress bar
        prog_bg = tk.Canvas(card, height=6, bg=SURF3, highlightthickness=0)
        prog_bg.pack(fill="x", padx=14, pady=2)
        prog_bg.update_idletasks()
        pw = prog_bg.winfo_width() or 400
        prog_bg.create_rectangle(0, 0, int(pw * pct / 100), 6,
                                  fill=ACCENT2, outline="")

        tk.Label(card, text=f"{g['current']} / {g['target']}",
                 bg=SURF, fg=MUTED2, font=MONO_SM).pack(
                 anchor="w", padx=14, pady=(2, 8))

        # Actions
        acts = tk.Frame(card, bg=SURF)
        acts.pack(fill="x", padx=14, pady=(0, 10))
        for amt in (1, 5, 10):
            tk.Button(acts, text=f"+{amt}", bg=SURF3, fg=TEXT,
                      relief="flat", cursor="hand2", font=MONO_SM,
                      command=lambda idx=i, a=amt: self._progress_goal(idx, a)
                      ).pack(side="left", padx=2, ipadx=8, ipady=4)
        tk.Button(acts, text="Delete", bg=SURF, fg=MUTED,
                  relief="flat", cursor="hand2", font=MONO_SM,
                  command=lambda idx=i: self._delete_goal(idx)
                  ).pack(side="right", ipadx=8, ipady=4)

    def _progress_goal(self, i, a):
        progress_goal(i, a)
        self._render_goals()

    def _delete_goal(self, i):
        delete_goal(i)
        self._render_goals()

    # ── STATS REFRESH ─────────────────────────────────────────
    def _refresh_stats(self):
        today_s  = get_today_stats()
        week_min = get_week_stats()
        streak   = get_streak()
        sessions = get_sessions()
        work_s   = [s for s in sessions if s.get("type") == "work"]
        total_m  = sum(s.get("duration", 0) for s in work_s)
        hours, mins = divmod(total_m, 60)

        self.stat_today._val.config(text=f"{today_s['minutes']} min")
        self.stat_week._val.config(text=f"{week_min} min")
        self.stat_all._val.config(text=f"{hours}h {mins}m")
        self.stat_streak._val.config(text=f"{streak} days")

        self.tip_label.config(
            text=f"Take a break every {CFG['sessions_before_long_break']} sessions  ·  "
                 "Stay hydrated  ·  Remove distractions for deep work")

    def _refresh_all(self):
        self._refresh_stats()
        self._render_todos()
        self._render_habits()
        self._render_goals()
        self._draw_bars()
        self._draw_predictions()


# ── Scrollable Frame Helper ───────────────────────────────────
class _ScrollFrame(tk.Frame):
    """Lightweight vertically-scrollable container."""
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        canvas = tk.Canvas(self, bg=kw.get("bg", BG), highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=kw.get("bg", BG))

        self.inner.bind("<Configure>",
                        lambda e: canvas.configure(
                            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")


# ── Entry point ───────────────────────────────────────────────
def main():
    root = tk.Tk()
    FocusTrackApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()