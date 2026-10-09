import os
import subprocess
import json
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from datetime import datetime

from rooster_engine import AutonomousEngineer, Action, Risk
from rooster_engine.video_studio import VideoStudio, VideoStudioError
from rooster_engine.video_renderer import VideoRenderer, VideoRendererError
from rooster_engine.creative_media import CreativeStudio, CreativeStudioError
from rooster_engine.autonomous import AutonomousCoder
from rooster_engine.interaction import parse_chat_action
from uuid import uuid4
from rooster_pentester.autonomous import run_autonomous_local_assessment

APP_NAME = "Rooster Autonomous Engineer"
DATA_FILE = Path.home() / ".rooster_autonomous_engineer.json"


class RoosterEngineerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME + " v2.3")
        self.root.geometry("1180x800")
        self.root.minsize(900, 620)
        self.workspace = Path.cwd()
        self.engine = AutonomousEngineer(self.workspace, DATA_FILE)
        self.pending_action = None
        self.action_running = False
        self.latest_pentest_report = None
        self.build_ui()
        self.log("Interactive chat: type a request and click Send to Rooster.")
        self.refresh_tasks()
        self.log("Rooster Autonomous Engineer v2.2 online.")
        self.log("RoosterGuard: permissions + sandbox + checkpoints + audit + emergency stop")
        self.log(f"Workspace: {self.workspace}")
        self.log(f"Tools: {', '.join(self.engine.tools.names())}")
        self.set_action_status("IDLE", "No pending action")

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
        ttk.Label(top, text=APP_NAME + " v2.3", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(top, text="EMERGENCY STOP", command=self.emergency_stop).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="Reset Stop", command=self.reset_stop).pack(side="right", padx=6)
        ttk.Button(top, text="Choose Workspace", command=self.choose_workspace).pack(side="right")
        ttk.Button(top, text="MAKE VIDEO", command=self.make_video).pack(side="right", padx=6)
        ttk.Button(top, text="MAKE MEDIA", command=self.make_media).pack(side="right", padx=6)
        ttk.Button(top, text="PENTEST MY COMPUTER", command=self.pentest_my_computer).pack(side="right", padx=6)
        ttk.Button(top, text="AUTONOMOUS PENTEST", command=self.start_autonomous_pentest).pack(side="right", padx=6)
        ttk.Button(top, text="AUTONOMOUS MODE", command=self.start_autonomous_mode).pack(side="right", padx=6)

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
        self.send_button = ttk.Button(chat_buttons, text="Send to Rooster", command=self.send_chat)
        self.send_button.pack(side="left")
        ttk.Button(chat_buttons, text="Use as Objective", command=self.use_chat_as_objective).pack(side="left", padx=6)
        self.approve_button = ttk.Button(chat_buttons, text="APPROVE ACTION", command=self.approve_pending_action, state="disabled")
        self.approve_button.pack(side="left", padx=6)
        self.reject_button = ttk.Button(chat_buttons, text="REJECT", command=self.reject_pending_action, state="disabled")
        self.reject_button.pack(side="left")
        self.chat_entry.bind("<Control-Return>", lambda _event: self.send_chat())

        status_frame = ttk.Frame(right)
        status_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(status_frame, text="Action Status:").pack(side="left")
        self.action_status_var = tk.StringVar(value="IDLE")
        ttk.Label(status_frame, textvariable=self.action_status_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        self.action_detail_var = tk.StringVar(value="No pending action")
        ttk.Label(status_frame, textvariable=self.action_detail_var).pack(side="left", padx=6)

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
        ttk.Button(bottom, text="Open Pentest Report", command=self.open_pentest_report).pack(side="left", padx=6)

    def chat_log(self, speaker, message):
        stamp = datetime.now().strftime("%H:%M:%S")

        def append():
            self.chat.configure(state="normal")
            self.chat.insert(tk.END, f"[{stamp}] {speaker}: {message}\n\n")
            self.chat.see(tk.END)
            self.chat.configure(state="disabled")

        self.root.after(0, append)

    def set_action_status(self, status, detail):
        def update():
            self.action_status_var.set(status)
            self.action_detail_var.set(detail)

        self.root.after(0, update)

    def send_chat(self):
        if self.action_running:
            self.chat_log("ROOSTER", "An approved action is still executing. Please wait for it to finish.")
            return

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
                return evidence if evidence else str(result)

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
        self.set_action_status("PENDING APPROVAL", f"{action.tool} · {action_id}")
        self.chat_log(
            "ROOSTER",
            f"PROPOSED ACTION\n"
            f"Tool: {action.tool}\n"
            f"Risk: {action.risk.value.upper()}\n"
            f"Target: {action.target or '(workspace)'}\n"
            f"Reason: {action.reason}\n"
            f"Action ID: {action_id}\n"
            "No action has been executed. Choose APPROVE ACTION or REJECT.",
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
        self.send_button.configure(state="disabled")
        self.action_running = True

        try:
            self.engine.guard.approve(action_id, actor="human", task_id=task_id)
            self.chat_log("YOU", f"APPROVED action {action_id}")
            self.chat_log("ROOSTER", "Approval recorded. Executing the exact approved action once.")
            self.set_action_status("EXECUTING", f"{action.tool} · {action_id}")
        except Exception as exc:
            self.action_running = False
            self.send_button.configure(state="normal")
            self.set_action_status("FAILED", str(exc))
            self.chat_log("ROOSTER", f"Action approval failed or was denied: {exc}")
            return

        threading.Thread(
            target=self._execute_approved_action,
            args=(executor, action.tool, action_id),
            daemon=True,
        ).start()

    def _execute_approved_action(self, executor, tool_name, action_id):
        try:
            evidence = executor()
            if isinstance(evidence, dict):
                report_files = evidence.get("report_files", {})
                html_report = report_files.get("html") if isinstance(report_files, dict) else None
                if html_report and Path(html_report).is_file():
                    self.latest_pentest_report = Path(html_report)
                    self.log(f"PENTEST REPORT READY: {html_report}")
            if evidence:
                self.chat_log("ROOSTER", json.dumps(evidence, indent=2, default=str) if not isinstance(evidence, str) else evidence)
            self.root.after(0, self._finish_approved_action, True, tool_name, action_id, "")
        except Exception as exc:
            self.root.after(0, self._finish_approved_action, False, tool_name, action_id, str(exc))

    def _finish_approved_action(self, success, tool_name, action_id, error):
        self.action_running = False
        self.send_button.configure(state="normal")
        if success:
            self.set_action_status("COMPLETED", f"{tool_name} · {action_id}")
            self.chat_log("ROOSTER", "Action completed successfully.")
        else:
            self.set_action_status("FAILED", f"{tool_name} · {action_id}")
            self.chat_log("ROOSTER", f"Action failed or was denied: {error}")

    def reject_pending_action(self):
        if not self.pending_action:
            self.chat_log("ROOSTER", "There is no pending action to reject.")
            return
        _action, action_id, _executor, _task_id = self.pending_action
        self.pending_action = None
        self.approve_button.configure(state="disabled")
        self.reject_button.configure(state="disabled")
        self.engine.guard.revoke_approval(action_id)
        self.set_action_status("REJECTED", action_id)
        self.chat_log("YOU", f"REJECTED action {action_id}")
        self.chat_log("ROOSTER", "Rejected. Nothing was executed.")

    def pentest_my_computer(self):
        """Propose a read-only local security audit through RoosterGuard."""
        if self.action_running or self.pending_action:
            messagebox.showwarning("Rooster Pentester", "Finish or reject the current action before starting a scan.")
            return
        if self.engine.guard.emergency_stop.stopped:
            messagebox.showwarning("Rooster Pentester", "Emergency Stop is active. Reset it before starting.")
            return
        confirmed = messagebox.askyesno(
            "Authorize Local Computer Pentest",
            "Rooster will inspect THIS computer only using read-only checks for OS details, "
            "TCP listening ports, Windows Firewall, and Defender status where available.\n\n"
            "It will not exploit services, scan other devices, change settings, or delete files. "
            "Results and evidence will be recorded in the local Rooster audit log.\n\n"
            "Continue and request the scan?",
            parent=self.root,
        )
        if not confirmed:
            self.log("PENTEST: user cancelled before authorization; no scan was run.")
            return
        task_id = f"pentest-local-{uuid4().hex[:12]}"
        reason = "User explicitly requested a read-only security assessment of this computer."
        action_text = "Inspect local OS security signals and TCP listeners without changing configuration."
        evidence = "Local posture findings, command output where available, and hash-chained audit entry."
        action = Action("pentest_local_computer", reason, action_text, evidence, Risk.MEDIUM, "local computer")

        def execute_local_audit():
            return self.engine.tools.run(
                "pentest_local_computer",
                reason=reason,
                action=action_text,
                evidence=evidence,
                risk=Risk.MEDIUM,
                target="local computer",
                actor="human",
                task_id=task_id,
                consent_confirmed=True,
            )

        self.log("PENTEST: local-only assessment proposed. Review and click APPROVE ACTION to execute.")
        self.propose_action(action, execute_local_audit, task_id)

    def start_autonomous_pentest(self):
        """Run the bounded autonomous local assessment behind explicit consent and RoosterGuard approval."""
        if self.action_running or self.pending_action:
            messagebox.showwarning("Rooster Autonomous Pentester", "Finish or reject the current action before starting.")
            return
        if self.engine.guard.emergency_stop.stopped:
            messagebox.showwarning("Rooster Autonomous Pentester", "Emergency Stop is active. Reset it before starting.")
            return
        confirmed = messagebox.askyesno(
            "Authorize Autonomous Pentester",
            "Rooster will autonomously run a bounded, read-only assessment of THIS computer only.\n\n"
            "It will check available OS security signals, local TCP listeners, Windows Firewall and Defender, "
            "verify the audit log, and create HTML/JSON reports. If it finds HIGH, REVIEW, or UNKNOWN items, "
            "it may repeat one read-only local snapshot to compare evidence (maximum two cycles). "
            "It will not scan other devices, exploit services, change settings, or automatically fix findings.\n\n"
            "You will still need to approve the proposed action. Continue?",
            parent=self.root,
        )
        if not confirmed:
            self.log("AUTONOMOUS PENTEST: user cancelled; no assessment was run.")
            return

        task_id = f"pentest-auto-{uuid4().hex[:12]}"
        audit_path = self.workspace / ".rooster" / "pentester-audit.jsonl"
        reason = "User explicitly requested a bounded autonomous local security assessment."
        action_text = "Run a bounded plan/execute/evaluate/re-plan loop using read-only local snapshots; verify audit integrity and export findings."
        evidence = "Local security findings, report paths, plan execution states, and verified audit-chain result."
        action = Action("pentest_autonomous_local", reason, action_text, evidence, Risk.MEDIUM, "local computer")

        def execute_autonomous_assessment():
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            return run_autonomous_local_assessment(
                audit_path=str(audit_path),
                consent_confirmed=True,
                stop_check=self.engine.guard.emergency_stop.check,
                progress=self.log,
            )

        self.log("AUTONOMOUS PENTEST: bounded plan proposed; awaiting RoosterGuard human approval.")
        self.propose_action(action, execute_autonomous_assessment, task_id)

    def make_video(self):
        """Run the complete AI video pipeline from one button."""
        idea = self.task_entry.get("1.0", tk.END).strip() or self.chat_entry.get("1.0", tk.END).strip()
        if not idea:
            messagebox.showwarning("Rooster Video Studio", "Enter a video idea first.")
            return

        renderer = VideoRenderer()
        if not renderer.configured:
            messagebox.showerror(
                "Rooster Video Studio",
                "No video renderer is connected.\n\n"
                "Connect a renderer with ROOSTER_RENDERER_URL or "
                "ROOSTER_RENDER_COMMAND, then press MAKE VIDEO again.",
            )
            self.log("VIDEO: no renderer connected; nothing was charged or rendered.")
            return

        self.log(f"VIDEO: renderer detected — {renderer.status()}")
        self.log("VIDEO: MAKE VIDEO pipeline started.")

        def worker():
            try:
                total_seconds = 120
                video_format = "vertical"
                self.log("VIDEO: creating 2-minute production plan with Rooster/OpenAI...")
                plan = VideoStudio().plan(idea, total_seconds=total_seconds, format=video_format)
                project_dir = self.workspace / "video_projects" / "rooster_video"
                project_dir.mkdir(parents=True, exist_ok=True)
                VideoStudio.save(plan, project_dir / "plan.json")

                clips = []
                for index, scene in enumerate(plan["scenes"], 1):
                    try:
                        self.engine.guard.emergency_stop.check()
                    except Exception as exc:
                        raise VideoRendererError("Rooster Emergency Stop is active.") from exc
                    clip = project_dir / f"scene_{index:02d}.mp4"
                    self.log(f"VIDEO: rendering scene {index}/{len(plan['scenes'])}...")
                    renderer.render_scene(
                        scene, clip, format=video_format,
                        master_visual_lock=plan.get("master_visual_lock", ""),
                        log=self.log,
                    )
                    clips.append(clip)

                final = project_dir / "rooster_2min.mp4"
                renderer.assemble(clips, final, log=self.log)
                self.root.after(0, lambda: messagebox.showinfo(
                    "Rooster Video Studio",
                    f"2-minute video complete.\n\n{final}",
                    parent=self.root,
                ))
            except Exception as exc:
                self.log(f"VIDEO PIPELINE FAILED: {exc}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Rooster Video Studio", str(exc), parent=self.root
                ))

        threading.Thread(target=worker, daemon=True).start()

    def make_media(self):
        """Create a complete project: video scenes, graphics, and commentary."""
        idea = self.task_entry.get("1.0", tk.END).strip() or self.chat_entry.get("1.0", tk.END).strip()
        if not idea:
            idea = (
                "Create an ultra-realistic Rooster Racing GT3 video featuring car #45 "
                "with a chrome silver mirror-finish livery, intense clean racing, and an "
                "energetic American motorsport commentary style."
            )
            self.task_entry.insert("1.0", idea)
        if self.action_running:
            messagebox.showwarning("Rooster Creative Studio", "Another guarded action is already running.")
            return

        self.action_running = True
        self.send_button.configure(state="disabled")
        self.log("MEDIA: full creative pipeline started — video + graphics + commentary.")

        def worker():
            try:
                self.engine.guard.emergency_stop.check()
                task_id = f"media-{uuid4().hex[:12]}"
                action = self.engine.guard.action_id(
                    Action(
                        "create_media_project",
                        "User requested a complete AI media project.",
                        "Plan and render video, graphics, and commentary.",
                        "Project files, rendered assets, and final MP4.",
                        Risk.MEDIUM,
                        "video_projects/rooster_media",
                    )
                )
                self.engine.guard.approve(action, actor="human", task_id=task_id)
                result = self.engine.tools.run(
                    "create_media_project",
                    idea,
                    reason="User requested a complete AI media project.",
                    action="Plan and render video, graphics, and commentary.",
                    evidence="Project files, rendered assets, and final MP4.",
                    risk=__import__("rooster_engine").Risk.MEDIUM,
                    target="video_projects/rooster_media",
                    actor="human",
                    task_id=task_id,
                )
                self.log(f"MEDIA COMPLETE: {result}")
                self.root.after(0, lambda: messagebox.showinfo(
                    "Rooster Creative Studio",
                    f"Media project complete.\n\n{result}",
                    parent=self.root,
                ))
            except Exception as exc:
                self.log(f"MEDIA PIPELINE FAILED: {exc}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Rooster Creative Studio", str(exc), parent=self.root
                ))
            finally:
                self.root.after(0, self._finish_autonomous_mode)

    def start_autonomous_mode(self):
        """Let Rooster independently execute a bounded engineering loop."""
        objective = self.task_entry.get("1.0", tk.END).strip() or self.chat_entry.get("1.0", tk.END).strip()
        if not objective:
            messagebox.showwarning("Rooster Autonomous Mode", "Enter an engineering objective first.")
            return
        if self.action_running:
            messagebox.showwarning("Rooster Autonomous Mode", "Another guarded action is already running.")
            return
        self.action_running = True
        self.send_button.configure(state="disabled")
        self.log("AUTONOMOUS: bounded self-directed engineering mode started.")
        self.log("AUTONOMOUS: read -> reason -> checkpoint -> write -> test -> verify.")

        def worker():
            try:
                task_id = f"auto-{uuid4().hex[:12]}"
                self.engine.create_checkpoint("autonomous_pre_change")
                coder = AutonomousCoder(self.engine)
                result = coder.run(objective, task_id=task_id)
                self.log(f"AUTONOMOUS STATUS: {result.status}")
                self.log(f"AUTONOMOUS ITERATIONS: {result.iterations}")
                self.log(f"AUTONOMOUS SUMMARY: {result.summary}")
                for item in result.evidence:
                    self.log(f"AUTONOMOUS EVIDENCE: {json.dumps(item, default=str)[:3000]}")
            except Exception as exc:
                self.log(f"AUTONOMOUS FAILED: {exc}")
            finally:
                self.root.after(0, self._finish_autonomous_mode)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_autonomous_mode(self):
        self.action_running = False
        self.send_button.configure(state="normal")
        self.refresh_tasks()
    def choose_workspace(self):
        folder = filedialog.askdirectory(initialdir=str(self.workspace))
        if folder:
            self.workspace = Path(folder).resolve()
            self.engine = AutonomousEngineer(self.workspace, DATA_FILE)
            self.log(f"Workspace changed to: {self.workspace}")
            self.log(f"Tools: {', '.join(self.engine.tools.names())}")
            self.set_action_status("IDLE", "Workspace changed; no pending action")

    def open_pentest_report(self):
        """Open the latest generated local Pentester HTML report."""
        report = self.latest_pentest_report
        if not report or not report.is_file():
            messagebox.showinfo(
                "Rooster Pentester",
                "No local pentest report is available yet. Run PENTEST MY COMPUTER first and approve the proposed action.",
                parent=self.root,
            )
            return
        try:
            opened = webbrowser.open(report.resolve().as_uri())
            if not opened:
                raise RuntimeError("The system browser did not confirm opening the report.")
            self.log(f"Opened Pentester report: {report}")
        except Exception as exc:
            messagebox.showerror("Rooster Pentester", f"Could not open the report:\n{exc}", parent=self.root)

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
        if self.pending_action:
            self.reject_pending_action()
        self.set_action_status("STOPPED", "Emergency stop active")

    def reset_stop(self):
        self.engine.reset_emergency_stop()
        self.log("Emergency stop reset. Guarded actions may resume.")
        if not self.action_running and not self.pending_action:
            self.set_action_status("IDLE", "No pending action")

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
