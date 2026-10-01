import os
import subprocess
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from datetime import datetime

from rooster_engine import AutonomousEngineer
from rooster_engine.interaction import parse_chat_action
from uuid import uuid4

APP_NAME = "Rooster Autonomous Engineer"
DATA_FILE = Path.home() / ".rooster_autonomous_engineer.json"


class RoosterEngineerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME + " v2.1")
        self.root.geometry("1180x780")
        self.root.minsize(900, 600)
        self.workspace = Path.cwd()
        self.engine = AutonomousEngineer(self.workspace, DATA_FILE)
        self.build_ui()
        self.log("Interactive chat: type a request and click Send to Rooster.")
        self.refresh_tasks()
        self.log("Rooster Autonomous Engineer v2.1 online.")
        self.log("RoosterGuard: permissions + sandbox + checkpoints + audit + emergency stop")
        self.log(f"Workspace: {self.workspace}")
        self.log(f"Tools: {', '.join(self.engine.tools.names())}")

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.root.after(0, lambda: (self.activity.insert(tk.END, f"[{stamp}] {message}\n"), self.activity.see(tk.END)))

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME + " v2.1", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(top, text="EMERGENCY STOP", command=self.emergency_stop).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="Reset Stop", command=self.reset_stop).pack(side="right", padx=6)
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

        ttk.Label(right, text="Talk to Rooster").pack(anchor="w")
        self.chat = scrolledtext.ScrolledText(right, height=10, wrap="word", state="disabled")
        self.chat.pack(fill="x", pady=(4, 6))
        self.chat_entry = tk.Text(right, height=3, wrap="word")
        self.chat_entry.pack(fill="x", pady=(0, 6))
        chat_buttons = ttk.Frame(right)
        chat_buttons.pack(fill="x", pady=(0, 6))
        ttk.Button(chat_buttons, text="Send to Rooster", command=self.send_chat).pack(side="left")
        ttk.Button(chat_buttons, text="Use as Objective", command=self.use_chat_as_objective).pack(side="left", padx=6)
        self.approve_button = ttk.Button(chat_buttons, text="APPROVE ACTION", command=self.approve_pending_action, state="disabled")
        self.approve_button.pack(side="left", padx=6)
        self.reject_button = ttk.Button(chat_buttons, text="REJECT", command=self.reject_pending_action, state="disabled")
        self.reject_button.pack(side="left")
        self.pending_action = None
        self.chat_entry.bind("<Control-Return>", lambda _event: self.send_chat())

        ttk.Label(right, text="Live Activity / Audit View").pack(anchor="w")
        self.activity = scrolledtext.ScrolledText(right, wrap="word")
        self.activity.pack(fill="both", expand=True, pady=4)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text="Open Workspace", command=self.open_workspace).pack(side="left")
        ttk.Button(bottom, text="Inspect Files", command=self.inspect_workspace).pack(side="left", padx=6)
        ttk.Button(bottom, text="Run Git Status", command=self.git_status).pack(side="left")
        ttk.Button(bottom, text="Checkpoint", command=self.create_checkpoint).pack(side="left", padx=6)
        ttk.Button(bottom, text="Save Task Log", command=self.save_log).pack(side="left")


    def chat_log(self, speaker, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert(tk.END, f"[{stamp}] {speaker}: {message}\n\n")
        self.chat.see(tk.END)
        self.chat.configure(state="disabled")

    def send_chat(self):
        message = self.chat_entry.get("1.0", tk.END).strip()
        if not message:
            return
        self.chat_entry.delete("1.0", tk.END)
        self.chat_log("YOU", message)

        action = parse_chat_action(message)
        if action is not None:
            task_id = f"chat-{uuid4().hex[:12]}"

            def execute_approved_action():
                result = self.engine.tools.run(
                    action.tool,
                    reason=action.reason,
                    action=action.action,
                    evidence=action.evidence,
                    risk=action.risk,
                    target=action.target,
                    actor="human",
                    task_id=task_id,
                )
                evidence = getattr(result, "evidence", None)
                if evidence:
                    self.chat_log("ROOSTER", json.dumps(evidence, indent=2, default=str))
                else:
                    self.chat_log("ROOSTER", str(result))

            self.propose_action(action, execute_approved_action, task_id)
            return

        self.chat_log(
            "ROOSTER",
            "I’ll inspect the workspace and produce a guarded engineering report. "
            "The current analysis path does not modify project files.",
        )
        self.task_entry.delete("1.0", tk.END)
        self.task_entry.insert("1.0", message)
        self.start_task()

    def use_chat_as_objective(self):
        message = self.chat_entry.get("1.0", tk.END).strip()
        if not message:
            return
        self.task_entry.delete("1.0", tk.END)
        self.task_entry.insert("1.0", message)
        self.chat_log("SYSTEM", "Request copied to Engineering Objective. Review it, then click Plan & Run.")


    def show_chat_response(self, message):
        self.chat_log("ROOSTER", message)

    def propose_action(self, action, executor, task_id=""):
        """Queue one exact guarded action for explicit human approval."""
        action_id = self.engine.guard.action_id(action)
        self.pending_action = (action, action_id, executor, task_id)
        self.approve_button.configure(state="normal")
        self.reject_button.configure(state="normal")
        self.chat_log(
            "ROOSTER",
            f"PROPOSED ACTION\\n"
            f"Tool: {action.tool}\\n"
            f"Risk: {action.risk.value.upper()}\\n"
            f"Target: {action.target or '(workspace)'}\\n"
            f"Reason: {action.reason}\\n"
            f"Action ID: {action_id}\\n"
            "No action has been executed. Choose APPROVE ACTION or REJECT."
        )
        return action_id

    def approve_pending_action(self):
        if not self.pending_action:
            self.chat_log("ROOSTER", "There is no pending action to approve.")
            return
        action, action_id, executor, task_id = self.pending_action
        self.pending_action = None
        self.approve_button.configure(state="disabled")
        self.reject_button.configure(state="disabled")
        try:
            self.engine.guard.approve(action_id, actor="human", task_id=task_id)
            self.chat_log("YOU", f"APPROVED action {action_id}")
            self.chat_log("ROOSTER", "Approval recorded. Executing the exact approved action once.")
            executor()
            self.chat_log("ROOSTER", "Action completed successfully.")
        except Exception as exc:
            self.chat_log("ROOSTER", f"Action failed or was denied: {exc}")

    def reject_pending_action(self):
        if not self.pending_action:
            return
        _action, action_id, _executor, _task_id = self.pending_action
        self.pending_action = None
        self.approve_button.configure(state="disabled")
        self.reject_button.configure(state="disabled")
        self.engine.guard.revoke_approval(action_id)
        self.chat_log("YOU", f"REJECTED action {action_id}")
        self.chat_log("ROOSTER", "Rejected. Nothing was executed.")

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

    def create_checkpoint(self):
        try:
            path = self.engine.create_checkpoint("manual")
            self.log(f"CHECKPOINT CREATED: {path}")
        except Exception as exc:
            self.log(f"Checkpoint failed: {exc}")

    def emergency_stop(self):
        self.engine.emergency_stop()
        self.log("!!! EMERGENCY STOP ACTIVE — all guarded actions blocked !!!")

    def reset_stop(self):
        self.engine.reset_emergency_stop()
        self.log("Emergency stop reset. Guarded actions may resume.")

    def start_task(self):
        objective = self.task_entry.get("1.0", tk.END).strip()
        if not objective:
            messagebox.showwarning("Rooster", "Enter an engineering objective first.")
            return
        self.log(f"OBJECTIVE: {objective}")
        self.log("REASON → ACTION → EVIDENCE")
        rationale = self.engine.reason_action_evidence(objective)
        self.log(f"REASON: {rationale['reason']}")
        self.log(f"ACTION: {rationale['action']}")
        self.log(f"EVIDENCE: {rationale['evidence']}")
        self.log("PLAN:")
        for index, step in enumerate(self.engine.plan(objective), 1):
            self.log(f"  {index}. {step}")
        threading.Thread(target=self.run_task, args=(objective,), daemon=True).start()

    def run_task(self, objective):
        task = self.engine.run(objective)
        self.log(f"TASK STATUS: {task.status}")
        if task.status == "completed":
            try:
                result = json.loads(task.result)
                analysis = result.get("analysis", {})
                files_read = analysis.get("files_read", [])
                findings = analysis.get("findings", [])
                self.log("=" * 64)
                self.log("ROOSTER ENGINEERING REPORT")
                self.log(f"STATUS: {task.status.upper()}")
                self.log("=" * 64)
                self.log(f"[ANALYSIS] Local analyzer read {len(files_read)} source files.")
                for path in files_read:
                    self.log(f"  [READ] {path}")
                if findings:
                    self.log(f"FINDINGS: {len(findings)}")
                    for index, finding in enumerate(findings, 1):
                        priority = finding.get("priority", "INFO")
                        area = finding.get("area", "inspection")
                        evidence = finding.get("evidence", "")
                        recommendation = finding.get("recommendation", "")
                        self.log(f"FINDING {index}: {priority} — {area}")
                        self.log(f"  File: {finding.get('file', finding.get('path', 'not specified'))}")
                        self.log(f"  Evidence: {evidence}")
                        self.log(f"  Recommendation: {recommendation}")
                else:
                    self.log("FINDINGS: none returned by the local analyzer.")
                verification = result.get("verification", {})
                observation = verification.get("observation", {})
                checkpoint = verification.get("checkpoint", {})
                self.log("[VERIFICATION]")
                self.log(f"  Read-only: {analysis.get('read_only', False)}")
                self.log("  Workspace files modified: 0 (analysis path is read-only)")
                self.log(f"  Checkpoint: {checkpoint.get('checkpoint', result.get('checkpoint', 'unknown'))}")
                self.log(f"  Observation captured: {bool(observation)}")
                self.chat_log("ROOSTER", "Inspection complete. The engineering report in the audit panel contains the evidence and recommendations.")
                self.log("Local analysis completed without an AI credit/API call.")
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                self.log(f"Local analysis result could not be displayed: {exc}")
                self.log(task.result)
        else:
            self.log(f"ERROR: {task.result}")
        self.root.after(0, self.refresh_tasks)

    def refresh_tasks(self):
        self.task_list.delete(0, tk.END)
        for task in reversed(self.engine.tasks):
            self.task_list.insert(tk.END, f"[{task.status}] {task.objective}")

    def save_log(self):
        path = filedialog.asksaveasfilename(title="Save activity log", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            Path(path).write_text(self.activity.get("1.0", tk.END), encoding="utf-8")
            self.log(f"Saved activity log: {path}")


if __name__ == "__main__":
    root = tk.Tk()
    RoosterEngineerApp(root)
    root.mainloop()
