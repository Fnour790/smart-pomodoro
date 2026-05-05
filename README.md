# 🍅 FocusTrack — Smart Pomodoro AI

> A fully-featured Pomodoro timer with AI-powered focus predictions, habit tracking, goal management, and a sleek dark UI — all built with Python & Tkinter.

---

## ✨ Features

### 🕐 Smart Pomodoro Timer
- Fully configurable work, short break, and long break durations
- Automatic session cycling — short breaks between sessions, long break every N sessions
- Visual progress bar that fills as your session counts down
- Color-coded modes: **orange** for deep focus, **green** for short break, **purple** for long break
- Sound notifications when a session or break ends (rising beeps for work done, descending for break done)

### 📊 Stats & Charts
- Today's focus time and session count
- This week's total focus minutes
- All-time focus hours and session count
- Current daily streak tracker
- Interactive 7-day bar chart showing your focus history

### 🤖 AI Insights
- Ask the AI anything about your focus patterns (e.g. *"predict my week"*, *"analyze my streak"*)
- 7-day focus time prediction chart powered by TimeFM
- Personalized tips and insights based on your session data

### ✅ To-do List
- Add, complete, and delete tasks
- Tasks persist across sessions
- Completed tasks shown with strikethrough styling

### 🔥 Habit Tracker
- Add daily habits to track
- Check off habits each day to build streaks
- Live streak counter per habit with flame badge

### 🎯 Goals
- Create goals with a custom target number
- Increment progress with +1, +5, +10 buttons
- Visual progress bar showing percentage complete
- Delete goals when finished

### ⚙ Custom Timer Settings
- Adjust work duration (5–120 min)
- Adjust short break (1–30 min)
- Adjust long break (5–60 min)
- Adjust sessions before long break (1–8)
- Settings saved automatically to `pomodoro_config.json`

---

## 🖥 Screenshots

> UI matches the `focustrack_pomodoro_ui.html` reference design — dark background (`#080b10`), JetBrains Mono-style monospace font, accent colors for each mode.

---

## 📁 Project Structure

```
smart-pomodoro/
├── main.py                  # Main app — UI, timer, all tabs
├── promodo_ai.py            # AI predictor & TodoManager
├── study_tracker.py         # Sessions, habits, goals, streaks
├── pomodoro_config.json     # Auto-generated timer settings
├── focustrack_pomodoro_ui.html  # Reference HTML UI design
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Tkinter (included with standard Python on Windows & macOS)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/smart-pomodoro.git
cd smart-pomodoro

# 2. (Optional) Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

---

## 🔔 Sound Notifications

FocusTrack plays beep notifications when a session or break ends:

| Event | Sound |
|---|---|
| Work session ends | Three rising beeps (880 → 1100 → 1320 Hz) |
| Break ends | Two descending beeps (1320 → 880 Hz) |

Sounds use Python's built-in `winsound` module on Windows — **no extra packages needed**. On other platforms it falls back to a terminal bell (`\a`). To use a custom `.wav` file instead, replace the `winsound.Beep(...)` calls in `_play_sound()` with:

```python
winsound.PlaySound("your_sound.wav", winsound.SND_FILENAME)
```

---

## ⚙ Configuration

Timer settings are saved automatically to `pomodoro_config.json` whenever you adjust them in the UI:

```json
{
  "work_minutes": 25,
  "short_break_minutes": 5,
  "long_break_minutes": 15,
  "sessions_before_long_break": 4
}
```

Delete this file to reset all settings to defaults.

---

## 🧠 AI Module (`promodo_ai.py`)

The `PomodoroPredictor` class powers the AI tab:

- `predict(n)` — returns a `n`-day focus time forecast
- `answer(question)` — responds to natural language questions about your focus patterns

The `TodoManager` class handles to-do persistence in memory across the session.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `tkinter` | UI framework (built-in) |
| `winsound` | Sound notifications on Windows (built-in) |
| `threading` | Non-blocking sound playback (built-in) |
| Any in `promodo_ai.py` / `study_tracker.py` | Depends on your AI/storage implementation |

---

## 🗺 Roadmap

- [ ] macOS / Linux sound support via `pygame` or `simpleaudio`
- [ ] Export session history to CSV
- [ ] Dark/light theme toggle
- [ ] Desktop tray icon with timer status
- [ ] Cloud sync for stats and habits

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

> Built with 🍅 and Python. Stay focused.