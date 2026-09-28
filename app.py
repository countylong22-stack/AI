import json
import os
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_NAME = "Rooster Autonomous Engineer"
DATA_FILE = Path.home() / ".rooster_autonomous_engineer.json"


class RoosterEngineer:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME + " v1")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.workspace = Path.cwd()
        self.tasks = self.load_tasks()
        self.build_ui()
        self.refresh_tasks()
        self.log("Rooster Autonomous Engineer v1 ready.")
        self.log(f"Workspace: {self.workspace}")

    def load_tasks(self):
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def save_tasks(self):
        DATA_FILE.write_text(
            json.dumps(self.tasks, indent=2),
            encoding="utf-8",
        )

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

        ttk.Label(
            top,
            text=APP_NAME,
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")

        ttk.Button(
            top,
            text="Choose Workspace",
            command=self.choose_workspace,
        ).pack(side="right")

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=2)

        ttk.Label(left, text="Engineering Objective").pack(anchor="w")

        self.task_entry = tk.Text(
            left,
            height=8,
            wrap="word",
        )
        self.task_entry.pack(fill="x", pady=(4, 8))

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(0, 10))

        ttk.Button(
            buttons,
            text="Plan & Run",
            command=self.start_task,
        ).pack(side="left", fill="x", expand=True)

        ttk.Button(
            buttons,
            text="Clear",
            command=lambda: self.task_entry.delete("1.0", tk.END),
        ).pack(side="left", padx=(6, 0))

        ttk.Label(left, text="Persistent Task Memory").pack(anchor="w")

        self.task_list = tk.Listbox(left, height=20)
        self.task_list.pack(fill="both", expand=True, pady=4)

        ttk.Label(right, text="Live Activity").pack(anchor="w")

        self.activity = scrolledtext.ScrolledText(
            right,
            wrap="word",
        )
        self.activity.pack(fill="both", expand=True, pady=4)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(6, 0))

        ttk.Button(
            bottom,
            text="Open Workspace",
            command=self.open_workspace,
        ).pack(side="left")

        ttk.Button(
            bottom,
            text="Run Git Status",
            command=self.git_status,
        ).pack(side="left", padx=6)

        ttk.Button(
            bottom,
            text="Save Task Log",
            command=self.save_log,
        ).pack(side="left")

    def choose_workspace(self):
        folder = filedialog.askdirectory(
            initialdir=str(self.workspace)
        )
        if folder:
            self.workspace = Path(folder)
            self.log(f"Workspace changed to: {self.workspace}")

    def open_workspace(self):
        try:
            os.startfile(self.workspace)
        except AttributeError:
            subprocess.Popen(["xdg-open", str(self.workspace)])

    def run_command(self, command, label):
        def worker():
            self.log(f"{label}: {' '.join(command)}")
            try:
                result = subprocess.run(
                    command,
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                output = (result.stdout + result.stderr).strip()
                self.log(output or "(no output)")
                self.log(f"{label} exit code: {result.returncode}")
            except Exception as exc:
                self.log(f"{label} failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def git_status(self):
        self.run_command(
            ["git", "status", "--short"],
            "Git status",
        )

    def start_task(self):
        task = self.task_entry.get("1.0", tk.END).strip()

        if not task:
            messagebox.showwarning(
                "Rooster",
                "Enter an engineering objective first.",
            )
            return

        record = {
            "created": datetime.now().isoformat(timespec="seconds"),
            "task": task,
            "status": "running",
            "workspace": str(self.workspace),
        }

        self.tasks.append(record)
        self.save_tasks()
        self.refresh_tasks()

        threading.Thread(
            target=self.execute_plan,
            args=(record,),
            daemon=True,
        ).start()

    def execute_plan(self, record):
        task = record["task"]

        self.log(f"OBJECTIVE: {task}")

        self.log("PLAN 1/5: Inspect workspace.")
        try:
            entries = sorted(
                self.workspace.iterdir(),
                key=lambda p: p.name.lower(),
            )
            self.log(f"Found {len(entries)} workspace entries.")

            for item in entries[:30]:
                kind = "DIR " if item.is_dir() else "FILE"
                self.log(f"  {kind} {item.name}")
        except Exception as exc:
            self.log(f"Workspace inspection failed: {exc}")

        self.log("PLAN 2/5: Detect project type.")
        markers = {
            "Python": ["pyproject.toml", "requirements.txt", "app.py"],
            "Node": ["package.json"],
            "Git": [".git"],
        }

        detected = []
        for project_type, names in markers.items():
            if any((self.workspace / name).exists() for name in names):
                detected.append(project_type)

        self.log(
            "Detected project types: "
            + (", ".join(detected) if detected else "Unknown")
        )

        self.log("PLAN 3/5: Identify available engineering tools.")
        self.log("  - Workspace file inspection")
        self.log("  - Git status")
        self.log("  - Local command runner")
        self.log("  - Persistent task memory")

        self.log("PLAN 4/5: Execute safe actions.")
        self.log(
            "v1 uses a safe-by-default execution model; "
            "destructive changes require future approval gates."
        )

        self.log("PLAN 5/5: Verify and report.")
        record["status"] = "completed"
        record["completed"] = datetime.now().isoformat(timespec="seconds")
        self.save_tasks()

        self.root.after(0, self.refresh_tasks)
        self.log("TASK COMPLETE: Engineering scaffold finished.")

    def refresh_tasks(self):
        self.task_list.delete(0, tk.END)

        for item in reversed(self.tasks):
            self.task_list.insert(
                tk.END,
                f"[{item.get('status', '?')}] "
                f"{item.get('task', '')}",
            )

    def save_log(self):
        path = filedialog.asksaveasfilename(
            title="Save activity log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
        )

        if path:
            Path(path).write_text(
                self.activity.get("1.0", tk.END),
                encoding="utf-8",
            )
            self.log(f"Saved activity log: {path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = RoosterEngineer(root)
    root.mainloop()
