import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from datetime import datetime

from rooster_engine import AutonomousEngineer

APP_NAME = "Rooster Autonomous Engineer"
DATA_FILE = Path.home() / ".rooster_autonomous_engineer.json"


class RoosterEngineerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME + " v1.1")
        self.root.geometry("1150x760")
        self.root.minsize(900, 600)
        self.workspace = Path.cwd()
        self.engine = AutonomousEngineer(self.workspace, DATA_FILE)
        self.build_ui()
        self.refresh_tasks()
        self.log("Rooster Autonomous Engineer v1.1 online.")
        self.log(f"Workspace: {self.workspace}")
        self.log(f"Tools: {', '.join(self.engine.tools.names())}")

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.root.after(
            0,
            lambda: (
                self.activity.insert(tk.END, f"[{stamp}] {message}\n"),
                self.activity.see(tk.END),
            ),
        )

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(top, text="Choose Workspace", command=self.choose_workspace).pack(side="right")

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=2)

        ttk.Label(left, text="Engineering Objective").pack(anchor="w")
        self.task_entry = tk.Text(left, height=8, wrap="word")
        self.task_entry.pack(fill="x", pady=(4, 8))

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(buttons, text="Plan & Run", command=self.start_task).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="Clear", command=lambda: self.task_entry.delete("1.0", tk.END)).pack(side="left", padx=(6, 0))

        ttk.Label(left, text="Persistent Task Memory").pack(anchor="w")
        self.task_list = tk.Listbox(left, height=20)
        self.task_list.pack(fill="both", expand=True, pady=4)

        ttk.Label(right, text="Live Activity").pack(anchor="w")
        self.activity = scrolledtext.ScrolledText(right, wrap="word")
        self.activity.pack(fill="both", expand=True, pady=4)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text="Open Workspace", command=self.open_workspace).pack(side="left")
        ttk.Button(bottom, text="Inspect Files", command=self.inspect_workspace).pack(side="left", padx=6)
        ttk.Button(bottom, text="Run Git Status", command=self.git_status).pack(side="left")
        ttk.Button(bottom, text="Save Task Log", command=self.save_log).pack(side="left", padx=6)

    def choose_workspace(self):
        folder = filedialog.askdirectory(initialdir=str(self.workspace))
        if folder:
            self.workspace = Path(folder).resolve()
            self.engine = AutonomousEngineer(self.workspace, DATA_FILE)
            self.log(f"Workspace changed to: {self.workspace}")
            self.log(f"Tools: {', '.join(self.engine.tools.names())}")

    def open_workspace(self):
        try:
            os.startfile(self.workspace)
        except AttributeError:
            subprocess.Popen(["xdg-open", str(self.workspace)])

    def inspect_workspace(self):
        try:
            items = self.engine.tools.run("inspect_workspace", 50)
            self.log(f"Workspace inspection: {len(items)} entries")
            for item in items:
                self.log(f"  {item['type']}: {item['name']}")
        except Exception as exc:
            self.log(f"Inspection failed: {exc}")

    def git_status(self):
        try:
            status = self.engine.tools.run("git_status")
            self.log(status or "(working tree clean)")
        except Exception as exc:
            self.log(f"Git status failed: {exc}")

    def start_task(self):
        objective = self.task_entry.get("1.0", tk.END).strip()
        if not objective:
            messagebox.showwarning("Rooster", "Enter an engineering objective first.")
            return

        self.log(f"OBJECTIVE: {objective}")
        self.log("PLAN:")
        for index, step in enumerate(self.engine.plan(objective), 1):
            self.log(f"  {index}. {step}")

        threading.Thread(target=self.run_task, args=(objective,), daemon=True).start()

    def run_task(self, objective):
        task = self.engine.run(objective)
        self.log(f"TASK STATUS: {task.status}")

        if task.status == "completed":
            self.log("Verification completed.")
            self.log("Available tools: " + ", ".join(self.engine.tools.names()))
        else:
            self.log(f"ERROR: {task.result}")

        self.root.after(0, self.refresh_tasks)

    def refresh_tasks(self):
        self.task_list.delete(0, tk.END)
        for task in reversed(self.engine.tasks):
            self.task_list.insert(
                tk.END,
                f"[{task.status}] {task.objective}",
            )

    def save_log(self):
        path = filedialog.asksaveasfilename(
            title="Save activity log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
        )
        if path:
            Path(path).write_text(self.activity.get("1.0", tk.END), encoding="utf-8")
            self.log(f"Saved activity log: {path}")


if __name__ == "__main__":
    root = tk.Tk()
    RoosterEngineerApp(root)
    root.mainloop()
