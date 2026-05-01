"""
promodo_ai.py
-------------
Application principale SmartPomodoro.
Interface tkinter dark-mode avec :
  - Timer Pomodoro (work / short break / long break)
  - Enregistrement automatique des sessions via StudyTracker
  - Prédictions TimesFM affichées dans un onglet dédié
  - Conseils Claude accessibles en un clic
  - Graphique d'historique (matplotlib embarqué)
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Matplotlib pour le graphique embarqué
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False
    print("⚠️  matplotlib non installé. pip install matplotlib")

from study_tracker import StudyTracker
from predictor import PomodoroPredictor, ClaudeAdvisor


# ===================================================================== #
#  THÈME DARK
# ===================================================================== #

COLORS = {
    "bg":        "#0d0f14",
    "surface":   "#161920",
    "surface2":  "#1e222d",
    "border":    "#2a2f3e",
    "accent":    "#e07840",
    "accent2":   "#4b8ef0",
    "text":      "#d4d6e0",
    "muted":     "#5a5f70",
    "green":     "#3ecf76",
    "red":       "#e05050",
    "yellow":    "#f0c040",
}

FONT_FAMILY = "Courier New"


# ===================================================================== #
#  FENÊTRE PRINCIPALE
# ===================================================================== #

class SmartPomodoro:
    """Application principale SmartPomodoro."""

    # Durées en secondes
    DURATIONS = {
        "work":        25 * 60,
        "short_break":  5 * 60,
        "long_break":  15 * 60,
    }

    SESSIONS_BEFORE_LONG_BREAK = 4

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SmartPomodoro — AI Focus Tracker")
        self.root.geometry("900x680")
        self.root.minsize(800, 600)
        self.root.configure(bg=COLORS["bg"])

        # État du timer
        self.mode: str          = "work"
        self.time_left: int     = self.DURATIONS["work"]
        self.running: bool      = False
        self.work_sessions: int = 0
        self._timer_job: Optional[str] = None

        # Modules métier
        self.tracker   = StudyTracker()
        self.predictor = PomodoroPredictor(horizon=7)
        self.advisor   = ClaudeAdvisor()   # lit ANTHROPIC_API_KEY

        # Construction UI
        self._apply_ttk_theme()
        self._build_ui()
        self._refresh_stats()

        # Raccourcis clavier
        self.root.bind("<space>", lambda e: self.toggle_timer())
        self.root.bind("<Escape>", lambda e: self.reset_timer())

    # ------------------------------------------------------------------ #
    #  THÈME TTK
    # ------------------------------------------------------------------ #

    def _apply_ttk_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TNotebook",
            background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab",
            background=COLORS["surface2"], foreground=COLORS["muted"],
            font=(FONT_FAMILY, 10), padding=[12, 6])
        style.map("TNotebook.Tab",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "#ffffff")])

        style.configure("TFrame",  background=COLORS["bg"])
        style.configure("TLabel",  background=COLORS["bg"], foreground=COLORS["text"],
            font=(FONT_FAMILY, 10))
        style.configure("TButton",
            background=COLORS["surface2"], foreground=COLORS["text"],
            font=(FONT_FAMILY, 10), relief="flat", borderwidth=0)
        style.map("TButton",
            background=[("active", COLORS["accent"])],
            foreground=[("active", "#ffffff")])

    # ------------------------------------------------------------------ #
    #  CONSTRUCTION UI
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self.root, bg=COLORS["surface"], height=48)
        header.pack(fill="x", padx=0, pady=0)

        tk.Label(header, text="◼ SMARTPOMODORO",
            font=(FONT_FAMILY, 13, "bold"),
            bg=COLORS["surface"], fg=COLORS["accent"]).pack(side="left", padx=16, pady=10)

        self.lbl_streak = tk.Label(header, text="🔥 streak : 0j",
            font=(FONT_FAMILY, 9), bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_streak.pack(side="right", padx=16)

        self.lbl_today = tk.Label(header, text="⏱ aujourd'hui : 0m",
            font=(FONT_FAMILY, 9), bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_today.pack(side="right", padx=8)

        # Notebook (onglets)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_tab_timer()
        self._build_tab_stats()
        self._build_tab_predict()
        self._build_tab_claude()

    # ------------------------------------------------------------------ #
    #  ONGLET 1 : TIMER
    # ------------------------------------------------------------------ #

    def _build_tab_timer(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  ⏱ Focus  ")

        # Mode selector
        mode_frame = tk.Frame(tab, bg=COLORS["bg"])
        mode_frame.pack(pady=(20, 0))

        self.mode_btns: dict[str, tk.Button] = {}
        modes = [("work", "🍅 Work"), ("short_break", "☕ Short Break"), ("long_break", "🌿 Long Break")]
        for key, label in modes:
            btn = tk.Button(mode_frame, text=label,
                font=(FONT_FAMILY, 9), relief="flat", padx=14, pady=6,
                bg=COLORS["surface2"], fg=COLORS["muted"],
                activebackground=COLORS["accent"], cursor="hand2",
                command=lambda k=key: self.set_mode(k))
            btn.pack(side="left", padx=4)
            self.mode_btns[key] = btn
        self._highlight_mode_btn()

        # Pixel cup (canvas)
        cup_canvas = tk.Canvas(tab, width=120, height=100,
            bg=COLORS["bg"], highlightthickness=0)
        cup_canvas.pack(pady=10)
        self._draw_pixel_cup(cup_canvas)

        # Timer display
        self.lbl_timer = tk.Label(tab, text=self._fmt_time(self.time_left),
            font=(FONT_FAMILY, 52, "bold"),
            bg=COLORS["bg"], fg=COLORS["text"])
        self.lbl_timer.pack()

        self.lbl_mode = tk.Label(tab, text="Deep Focus Mode",
            font=(FONT_FAMILY, 10), bg=COLORS["bg"], fg=COLORS["muted"])
        self.lbl_mode.pack(pady=(0, 8))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        progress_frame = tk.Frame(tab, bg=COLORS["bg"])
        progress_frame.pack(fill="x", padx=80)
        self.progress_bar = tk.Canvas(progress_frame, height=6,
            bg=COLORS["surface2"], highlightthickness=0)
        self.progress_bar.pack(fill="x")
        self.prog_fill = None

        # Boutons
        btn_frame = tk.Frame(tab, bg=COLORS["bg"])
        btn_frame.pack(pady=16)

        self.btn_start = tk.Button(btn_frame, text="▶  Start",
            font=(FONT_FAMILY, 11, "bold"), relief="flat",
            bg=COLORS["accent"], fg="#ffffff", padx=24, pady=10,
            activebackground="#c06030", cursor="hand2",
            command=self.toggle_timer)
        self.btn_start.pack(side="left", padx=6)

        tk.Button(btn_frame, text="↺  Reset",
            font=(FONT_FAMILY, 10), relief="flat",
            bg=COLORS["surface2"], fg=COLORS["muted"], padx=16, pady=10,
            cursor="hand2", command=self.reset_timer).pack(side="left", padx=6)

        tk.Button(btn_frame, text="⏭  Skip",
            font=(FONT_FAMILY, 10), relief="flat",
            bg=COLORS["surface2"], fg=COLORS["muted"], padx=16, pady=10,
            cursor="hand2", command=self.skip_session).pack(side="left", padx=6)

        # Sessions counter
        self.lbl_sessions = tk.Label(tab,
            text=f"Sessions aujourd'hui : {len(self.tracker.get_today_sessions())}",
            font=(FONT_FAMILY, 9), bg=COLORS["bg"], fg=COLORS["muted"])
        self.lbl_sessions.pack(pady=4)

    def _draw_pixel_cup(self, canvas: tk.Canvas) -> None:
        """Dessine une tasse pixel-art sur le canvas."""
        px = 8  # taille d'un pixel
        ox, oy = 20, 10  # offset

        pixels = [
            # (col, row, color)
            # Body
            *[(c, r, COLORS["accent"]) for r in range(2, 7) for c in range(2, 10)],
            # Handle
            *[(10, r, "#c06030") for r in range(3, 6)],
            # Top rim
            *[(c, 1, "#c06030") for c in range(1, 11)],
            # Base
            *[(c, 7, "#c06030") for c in range(2, 10)],
            *[(c, 8, "#8a4020") for c in range(3, 9)],
            # Liquid surface shine
            *[(c, 3, "#f0a060") for c in range(3, 8)],
        ]
        for col, row, color in pixels:
            x1, y1 = ox + col * px, oy + row * px
            canvas.create_rectangle(x1, y1, x1 + px, y1 + px,
                fill=color, outline="")

    # ------------------------------------------------------------------ #
    #  ONGLET 2 : STATS
    # ------------------------------------------------------------------ #

    def _build_tab_stats(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  📊 Stats  ")

        # KPI cards
        kpi_frame = tk.Frame(tab, bg=COLORS["bg"])
        kpi_frame.pack(fill="x", padx=16, pady=16)

        self.kpi_vars: dict[str, tk.StringVar] = {}
        kpis = [
            ("today",   "⏱ Aujourd'hui",  "0m"),
            ("week",    "📅 Semaine",      "0m"),
            ("streak",  "🔥 Streak",       "0j"),
            ("sessions","🍅 Sessions/j",   "0"),
        ]
        for i, (key, label, default) in enumerate(kpis):
            var = tk.StringVar(value=default)
            self.kpi_vars[key] = var
            card = tk.Frame(kpi_frame, bg=COLORS["surface"],
                padx=14, pady=12, relief="flat")
            card.grid(row=0, column=i, padx=6, sticky="ew")
            kpi_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=label, font=(FONT_FAMILY, 8),
                bg=COLORS["surface"], fg=COLORS["muted"]).pack(anchor="w")
            tk.Label(card, textvariable=var, font=(FONT_FAMILY, 18, "bold"),
                bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(4, 0))

        # Graphique historique
        if MPL_AVAILABLE:
            graph_frame = tk.Frame(tab, bg=COLORS["bg"])
            graph_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

            self.fig = Figure(figsize=(8, 3), facecolor=COLORS["bg"])
            self.ax  = self.fig.add_subplot(111)
            self._style_ax(self.ax)

            self.canvas_mpl = FigureCanvasTkAgg(self.fig, master=graph_frame)
            self.canvas_mpl.get_tk_widget().pack(fill="both", expand=True)
            self._draw_history_chart()
        else:
            tk.Label(tab, text="pip install matplotlib pour le graphique",
                font=(FONT_FAMILY, 10), bg=COLORS["bg"],
                fg=COLORS["muted"]).pack(pady=40)

        tk.Button(tab, text="↻ Actualiser",
            font=(FONT_FAMILY, 9), relief="flat",
            bg=COLORS["surface2"], fg=COLORS["muted"], padx=12, pady=6,
            cursor="hand2", command=self._refresh_stats).pack(pady=8)

    def _style_ax(self, ax) -> None:
        ax.set_facecolor(COLORS["surface"])
        ax.tick_params(colors=COLORS["muted"], labelsize=7)
        ax.spines[:].set_color(COLORS["border"])
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)
        self.fig.tight_layout(pad=1.5)

    def _draw_history_chart(self) -> None:
        if not MPL_AVAILABLE:
            return
        self.ax.clear()
        self._style_ax(self.ax)

        totals = self.tracker.get_daily_totals(30)
        if not totals:
            self.ax.text(0.5, 0.5, "Pas encore de données",
                ha="center", va="center", color=COLORS["muted"],
                transform=self.ax.transAxes, fontsize=10)
        else:
            dates  = list(totals.keys())
            values = [v / 60 for v in totals.values()]  # → heures
            colors_bars = [
                COLORS["accent"] if i == len(values) - 1 else COLORS["accent2"]
                for i in range(len(values))
            ]
            self.ax.bar(range(len(dates)), values, color=colors_bars, width=0.7)
            self.ax.set_xticks(range(0, len(dates), max(1, len(dates) // 7)))
            self.ax.set_xticklabels(
                [dates[i][-5:] for i in range(0, len(dates), max(1, len(dates) // 7))],
                rotation=30, ha="right", fontsize=7, color=COLORS["muted"])
            self.ax.set_ylabel("Heures", color=COLORS["muted"], fontsize=8)
            self.ax.set_title("Focus — 30 derniers jours",
                color=COLORS["text"], fontsize=9, pad=8)

        self.canvas_mpl.draw()

    # ------------------------------------------------------------------ #
    #  ONGLET 3 : PRÉDICTIONS TIMESFM
    # ------------------------------------------------------------------ #

    def _build_tab_predict(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  🔮 Predict  ")

        header = tk.Frame(tab, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(header, text="✦ Prédictions TimesFM",
            font=(FONT_FAMILY, 12, "bold"),
            bg=COLORS["bg"], fg=COLORS["accent2"]).pack(side="left")

        tk.Button(header, text="⟳ Lancer la prédiction",
            font=(FONT_FAMILY, 9), relief="flat",
            bg=COLORS["accent2"], fg="#ffffff", padx=12, pady=5,
            cursor="hand2", command=self._run_prediction).pack(side="right")

        # Zone de résultats
        self.predict_frame = tk.Frame(tab, bg=COLORS["bg"])
        self.predict_frame.pack(fill="both", expand=True, padx=16)

        self.lbl_predict_status = tk.Label(self.predict_frame,
            text="Cliquez sur 'Lancer la prédiction' pour démarrer.",
            font=(FONT_FAMILY, 10), bg=COLORS["bg"], fg=COLORS["muted"])
        self.lbl_predict_status.pack(pady=40)

        # Graphique prédiction
        if MPL_AVAILABLE:
            self.fig_pred = Figure(figsize=(8, 2.5), facecolor=COLORS["bg"])
            self.ax_pred  = self.fig_pred.add_subplot(111)
            self._style_ax(self.ax_pred)
            self.canvas_pred = FigureCanvasTkAgg(self.fig_pred,
                master=self.predict_frame)
            self.canvas_pred.get_tk_widget().pack(fill="x", pady=8)

    def _run_prediction(self) -> None:
        """Lance TimesFM dans un thread pour ne pas bloquer l'UI."""
        self.lbl_predict_status.config(
            text="⏳ Calcul en cours (TimesFM)...", fg=COLORS["yellow"])
        self.root.update()

        def _worker():
            series = self.tracker.get_time_series_for_prediction(60)
            preds  = self.predictor.predict(series)
            rich   = self.predictor.format_predictions(preds)
            self.root.after(0, lambda: self._display_predictions(rich))

        threading.Thread(target=_worker, daemon=True).start()

    def _display_predictions(self, predictions: list[dict]) -> None:
        self.lbl_predict_status.config(
            text="✅ Prédictions pour les 7 prochains jours", fg=COLORS["green"])

        # Barres textuelles
        for widget in self.predict_frame.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.destroy()

        bars_frame = tk.Frame(self.predict_frame, bg=COLORS["bg"])
        bars_frame.pack(fill="x", pady=8)

        level_colors = {
            "excellent": COLORS["green"],
            "good":      COLORS["accent2"],
            "moderate":  COLORS["yellow"],
            "low":       COLORS["muted"],
        }

        for p in predictions:
            row = tk.Frame(bars_frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=3)

            tk.Label(row, text=p["day"][:10], width=14, anchor="w",
                font=(FONT_FAMILY, 9), bg=COLORS["bg"],
                fg=COLORS["muted"]).pack(side="left")

            bar_bg = tk.Frame(row, bg=COLORS["surface2"], height=14, width=300)
            bar_bg.pack(side="left", padx=4)
            bar_bg.pack_propagate(False)

            fill_w = int(p["minutes"] / 180 * 300)
            color  = level_colors.get(p["level"], COLORS["accent2"])
            tk.Frame(bar_bg, bg=color, width=fill_w, height=14).place(x=0, y=0)

            tk.Label(row, text=p["formatted"], width=8, anchor="w",
                font=(FONT_FAMILY, 9, "bold"),
                bg=COLORS["bg"], fg=color).pack(side="left")

        # Graphique matplotlib
        if MPL_AVAILABLE:
            self.ax_pred.clear()
            self._style_ax(self.ax_pred)
            days   = [p["day"][:6] for p in predictions]
            values = [p["minutes"] / 60 for p in predictions]
            cols   = [level_colors.get(p["level"], COLORS["accent2"]) for p in predictions]
            self.ax_pred.bar(days, values, color=cols, width=0.6)
            self.ax_pred.set_ylabel("Heures", color=COLORS["muted"], fontsize=8)
            self.ax_pred.set_title("Prévisions focus (7j)",
                color=COLORS["text"], fontsize=9)
            self.canvas_pred.draw()

        # Stocke pour Claude
        self._last_predictions = predictions

    # ------------------------------------------------------------------ #
    #  ONGLET 4 : CLAUDE ADVISOR
    # ------------------------------------------------------------------ #

    def _build_tab_claude(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  🤖 Claude  ")

        tk.Label(tab, text="🤖 Conseils personnalisés — Claude AI",
            font=(FONT_FAMILY, 12, "bold"),
            bg=COLORS["bg"], fg=COLORS["accent"]).pack(padx=16, pady=(16, 4), anchor="w")

        tk.Label(tab,
            text="Claude analyse votre historique + prédictions TimesFM pour vous guider.",
            font=(FONT_FAMILY, 9), bg=COLORS["bg"], fg=COLORS["muted"]).pack(
            padx=16, anchor="w")

        # Champ question
        q_frame = tk.Frame(tab, bg=COLORS["bg"])
        q_frame.pack(fill="x", padx=16, pady=10)

        tk.Label(q_frame, text="Votre question :",
            font=(FONT_FAMILY, 9), bg=COLORS["bg"],
            fg=COLORS["muted"]).pack(anchor="w")

        self.entry_question = tk.Entry(q_frame,
            font=(FONT_FAMILY, 10), bg=COLORS["surface2"],
            fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", bd=8)
        self.entry_question.pack(fill="x", pady=4)
        self.entry_question.insert(0, "Comment améliorer ma productivité ?")
        self.entry_question.bind("<Return>", lambda e: self._ask_claude())

        tk.Button(q_frame, text="→ Demander à Claude",
            font=(FONT_FAMILY, 10, "bold"), relief="flat",
            bg=COLORS["accent"], fg="#ffffff", padx=16, pady=8,
            cursor="hand2", command=self._ask_claude).pack(anchor="e", pady=4)

        # Réponse
        self.txt_claude = scrolledtext.ScrolledText(tab,
            font=(FONT_FAMILY, 10), bg=COLORS["surface"],
            fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", padx=12, pady=10, wrap="word",
            state="disabled")
        self.txt_claude.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Config tags couleur
        self.txt_claude.tag_config("advice", foreground=COLORS["text"])
        self.txt_claude.tag_config("loading", foreground=COLORS["yellow"])
        self.txt_claude.tag_config("error", foreground=COLORS["red"])

    def _ask_claude(self) -> None:
        """Interroge Claude dans un thread."""
        question = self.entry_question.get().strip() or None
        self._set_claude_text(
            "⏳ Claude analyse vos données...\n", "loading")
        self.root.update()

        def _worker():
            stats   = self.tracker.summary_for_claude()
            preds   = getattr(self, "_last_predictions", [])
            advice  = self.advisor.get_advice(stats, preds, question)
            self.root.after(0, lambda: self._set_claude_text(advice, "advice"))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_claude_text(self, text: str, tag: str = "advice") -> None:
        self.txt_claude.config(state="normal")
        self.txt_claude.delete("1.0", "end")
        self.txt_claude.insert("1.0", text, tag)
        self.txt_claude.config(state="disabled")

    # ------------------------------------------------------------------ #
    #  LOGIQUE TIMER
    # ------------------------------------------------------------------ #

    def toggle_timer(self) -> None:
        if self.running:
            self._pause()
        else:
            self._start()

    def _start(self) -> None:
        self.running = True
        self.btn_start.config(text="⏸  Pause", bg=COLORS["surface2"],
            fg=COLORS["muted"])
        self._tick()

    def _pause(self) -> None:
        self.running = False
        if self._timer_job:
            self.root.after_cancel(self._timer_job)
        self.btn_start.config(text="▶  Reprendre", bg=COLORS["accent"],
            fg="#ffffff")

    def _tick(self) -> None:
        if not self.running:
            return
        if self.time_left > 0:
            self.time_left -= 1
            self._update_timer_display()
            self._timer_job = self.root.after(1000, self._tick)
        else:
            self._session_complete()

    def _session_complete(self) -> None:
        self.running = False
        completed_mode = self.mode

        # Enregistre la session
        if completed_mode == "work":
            self.work_sessions += 1
            duration = self.DURATIONS["work"] // 60
            self.tracker.add_session(duration, "work", completed=True)
            msg = f"🍅 Session de travail terminée !\nSessions complétées : {self.work_sessions}"
        else:
            duration = self.DURATIONS[completed_mode] // 60
            self.tracker.add_session(duration, completed_mode, completed=True)
            msg = "☕ Pause terminée ! Prêt à repartir ?"

        messagebox.showinfo("SmartPomodoro", msg)
        self._refresh_stats()

        # Passage automatique au mode suivant
        if completed_mode == "work":
            if self.work_sessions % self.SESSIONS_BEFORE_LONG_BREAK == 0:
                self.set_mode("long_break")
            else:
                self.set_mode("short_break")
        else:
            self.set_mode("work")

    def reset_timer(self) -> None:
        self.running = False
        if self._timer_job:
            self.root.after_cancel(self._timer_job)
        self.time_left = self.DURATIONS[self.mode]
        self._update_timer_display()
        self.btn_start.config(text="▶  Start",
            bg=COLORS["accent"], fg="#ffffff")

    def skip_session(self) -> None:
        self.running = False
        if self._timer_job:
            self.root.after_cancel(self._timer_job)
        # Enregistre comme non complétée
        if self.mode == "work":
            mins = (self.DURATIONS["work"] - self.time_left) // 60
            if mins > 0:
                self.tracker.add_session(mins, "work", completed=False)
        self._session_complete()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.time_left = self.DURATIONS[mode]
        self.running = False
        if self._timer_job:
            self.root.after_cancel(self._timer_job)
        self._update_timer_display()
        self._highlight_mode_btn()
        self.btn_start.config(text="▶  Start",
            bg=COLORS["accent"], fg="#ffffff")
        labels = {
            "work":        "Deep Focus Mode",
            "short_break": "Short Break ☕",
            "long_break":  "Long Break 🌿",
        }
        self.lbl_mode.config(text=labels[mode])

    def _highlight_mode_btn(self) -> None:
        for key, btn in self.mode_btns.items():
            if key == self.mode:
                btn.config(bg=COLORS["accent"], fg="#ffffff")
            else:
                btn.config(bg=COLORS["surface2"], fg=COLORS["muted"])

    # ------------------------------------------------------------------ #
    #  AFFICHAGE
    # ------------------------------------------------------------------ #

    def _update_timer_display(self) -> None:
        self.lbl_timer.config(text=self._fmt_time(self.time_left))
        total = self.DURATIONS[self.mode]
        elapsed = total - self.time_left
        pct = elapsed / total if total > 0 else 0

        # Redessine la barre de progression
        self.progress_bar.update_idletasks()
        w = self.progress_bar.winfo_width()
        self.progress_bar.delete("all")
        self.progress_bar.create_rectangle(0, 0, int(w * pct), 6,
            fill=COLORS["accent"], outline="")

    def _refresh_stats(self) -> None:
        """Met à jour les KPI cards, le header et le graphique."""
        today   = self.tracker.get_stats_today()
        weekly  = self.tracker.get_weekly_stats()
        streak  = self.tracker.get_streak()

        # Header
        self.lbl_today.config(
            text=f"⏱ {today['total_formatted']}")
        self.lbl_streak.config(text=f"🔥 {streak}j")

        # KPI
        if hasattr(self, "kpi_vars"):
            self.kpi_vars["today"].set(today["total_formatted"])
            self.kpi_vars["week"].set(weekly["total_formatted"])
            self.kpi_vars["streak"].set(f"{streak}j")
            avg_sessions = round(weekly["sessions_count"] / 7, 1)
            self.kpi_vars["sessions"].set(str(avg_sessions))

        # Label sessions
        if hasattr(self, "lbl_sessions"):
            self.lbl_sessions.config(
                text=f"Sessions aujourd'hui : {today['sessions_count']}")

        # Graphique
        if MPL_AVAILABLE and hasattr(self, "canvas_mpl"):
            self._draw_history_chart()

    # ------------------------------------------------------------------ #
    #  UTILITAIRES
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_time(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def run(self) -> None:
        """Lance la boucle principale tkinter."""
        self.root.mainloop()


# ===================================================================== #
#  POINT D'ENTRÉE
# ===================================================================== #

if __name__ == "__main__":
    app = SmartPomodoro()
    app.run()