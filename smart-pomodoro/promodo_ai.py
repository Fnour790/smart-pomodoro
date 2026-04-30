import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from datetime import datetime
from study_tracker import StudyTracker
from predictor import StudyPredictor

class SmartPomodoro:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🧠 AI-Powered Smart Pomodoro")
        self.root.geometry("500x600")
        self.root.configure(bg='#2c3e50')
        
        # Initialize components
        self.tracker = StudyTracker()
        self.predictor = StudyPredictor()
        
        # Timer state
        self.is_running = False
        self.time_left = 25 * 60  # 25 minutes in seconds
        self.current_mode = "study"  # study or break
        self.study_minutes = 0
        self.current_session_start = None
        
        # User settings
        self.study_goal = 120  # minutes per day
        self.energy_level = 5
        
        self.setup_ui()
        self.check_and_update_recommendation()
        
    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="🧠 AI-Powered Smart Pomodoro", 
                         font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white')
        title.pack(pady=20)
        
        # AI Recommendation Frame
        self.recommendation_frame = tk.Frame(self.root, bg='#34495e', relief=tk.RAISED, bd=2)
        self.recommendation_frame.pack(pady=10, padx=20, fill='x')
        
        self.recommendation_label = tk.Label(self.recommendation_frame, text="🤖 Analyzing your study patterns...", 
                                              font=('Arial', 12), bg='#34495e', fg='#ecf0f1', wraplength=450)
        self.recommendation_label.pack(pady=15, padx=10)
        
        # Timer Display
        self.timer_label = tk.Label(self.root, text="25:00", font=('Arial', 64, 'bold'), 
                                    bg='#2c3e50', fg='#2ecc71')
        self.timer_label.pack(pady=30)
        
        # Mode Label
        self.mode_label = tk.Label(self.root, text="📚 Study Time", font=('Arial', 14), 
                                   bg='#2c3e50', fg='#ecf0f1')
        self.mode_label.pack()
        
        # Buttons
        button_frame = tk.Frame(self.root, bg='#2c3e50')
        button_frame.pack(pady=20)
        
        self.start_button = tk.Button(button_frame, text="▶ Start", command=self.start_timer,
                                       font=('Arial', 12), bg='#27ae60', fg='white', padx=20)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = tk.Button(button_frame, text="⏸ Pause", command=self.pause_timer,
                                       font=('Arial', 12), bg='#f39c12', fg='white', padx=20, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = tk.Button(button_frame, text="🔄 Reset", command=self.reset_timer,
                                       font=('Arial', 12), bg='#e74c3c', fg='white', padx=20)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        # Progress Frame
        progress_frame = tk.Frame(self.root, bg='#2c3e50')
        progress_frame.pack(pady=20, padx=20, fill='x')
        
        tk.Label(progress_frame, text="Today's Progress:", font=('Arial', 10), 
                 bg='#2c3e50', fg='#bdc3c7').pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(pady=5)
        
        self.progress_label = tk.Label(progress_frame, text="0 / 120 minutes", 
                                       font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7')
        self.progress_label.pack()
        
        # Energy Level Slider
        energy_frame = tk.Frame(self.root, bg='#2c3e50')
        energy_frame.pack(pady=20, padx=20, fill='x')
        
        tk.Label(energy_frame, text="⚡ Energy Level (1-10):", font=('Arial', 10), 
                 bg='#2c3e50', fg='#bdc3c7').pack()
        
        self.energy_slider = tk.Scale(energy_frame, from_=1, to=10, orient=tk.HORIZONTAL,
                                       command=self.update_energy, bg='#2c3e50', fg='white',
                                       length=300)
        self.energy_slider.set(5)
        self.energy_slider.pack()
        
        # Goal Setting
        goal_frame = tk.Frame(self.root, bg='#2c3e50')
        goal_frame.pack(pady=10, padx=20, fill='x')
        
        tk.Label(goal_frame, text="🎯 Daily Goal (minutes):", font=('Arial', 10), 
                 bg='#2c3e50', fg='#bdc3c7').pack(side=tk.LEFT)
        
        self.goal_entry = tk.Entry(goal_frame, width=10, font=('Arial', 10))
        self.goal_entry.insert(0, "120")
        self.goal_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Button(goal_frame, text="Set", command=self.update_goal,
                  font=('Arial', 9), bg='#3498db', fg='white').pack(side=tk.LEFT)
        
    def update_energy(self, value):
        self.energy_level = int(value)
        self.check_and_update_recommendation()
    
    def update_goal(self):
        try:
            self.study_goal = int(self.goal_entry.get())
            self.update_progress_display()
            self.check_and_update_recommendation()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")
    
    def update_progress_display(self):
        self.progress_bar['maximum'] = self.study_goal
        self.progress_bar['value'] = self.study_minutes
        self.progress_label.config(text=f"{self.study_minutes} / {self.study_goal} minutes")
    
    def check_and_update_recommendation(self):
        """Get AI prediction and update recommendation"""
        def update():
            # Prepare historical data
            time_series, dates = self.tracker.prepare_timeseries_data(days_back=30)
            
            # Get prediction for today
            predictions, intervals = self.predictor.predict_study_time(time_series, days_to_predict=1)
            
            if predictions is not None:
                predicted_today = predictions[0]
                recommendation = self.predictor.get_study_recommendation(
                    predicted_today, 
                    self.energy_level, 
                    self.study_goal
                )
                
                # Update UI in main thread
                self.root.after(0, lambda: self.recommendation_label.config(
                    text=f"🤖 TimesFM Analysis:\n{recommendation['message']}"
                ))
            else:
                self.root.after(0, lambda: self.recommendation_label.config(
                    text="📊 Track a few more days of study for AI predictions!"
                ))
        
        # Run prediction in separate thread to not block UI
        threading.Thread(target=update, daemon=True).start()
    
    def start_timer(self):
        if not self.is_running:
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            if self.current_mode == "study":
                self.current_session_start = datetime.now()
            self.update_timer()
    
    def pause_timer(self):
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
    
    def reset_timer(self):
        self.is_running = False
        self.time_left = 25 * 60 if self.current_mode == "study" else 5 * 60
        self.update_display()
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
    
    def update_timer(self):
        if self.is_running and self.time_left > 0:
            self.time_left -= 1
            self.update_display()
            self.root.after(1000, self.update_timer)
        elif self.is_running and self.time_left == 0:
            self.timer_complete()
    
    def update_display(self):
        minutes = self.time_left // 60
        seconds = self.time_left % 60
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
    
    def timer_complete(self):
        self.is_running = False
        
        if self.current_mode == "study":
            # Record the completed study session
            session_duration = 25  # minutes
            self.study_minutes += session_duration
            self.tracker.add_session(session_duration)
            self.update_progress_display()
            
            # Check if goal is met with AI recommendation
            if self.study_minutes >= self.study_goal:
                messagebox.showinfo("Congratulations!", 
                                   f"🎉 You've achieved your daily goal of {self.study_goal} minutes!\nTake a well-deserved break!")
            
            # Switch to break mode
            self.current_mode = "break"
            self.mode_label.config(text="☕ Break Time", fg='#f39c12')
            self.time_left = 5 * 60
            messagebox.showinfo("Session Complete", "Great work! Time for a 5-minute break.")
            
            # Refresh AI recommendation after completing session
            self.check_and_update_recommendation()
            
        else:  # break mode complete
            self.current_mode = "study"
            self.mode_label.config(text="📚 Study Time", fg='#2ecc71')
            self.time_left = 25 * 60
            messagebox.showinfo("Break Over", "Break's over! Ready to study again?")
        
        self.update_display()
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
    
    def run(self):
        self.root.mainloop()

# Run the application
if __name__ == "__main__":
    app = SmartPomodoro()
    app.run()