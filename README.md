# Rooster Autonomous Engineer v2

Rooster v2 is a guarded autonomous engineering workspace for Windows and Python. It adds a policy boundary between the agent and its tools so autonomy is observable, interruptible, and approval-gated where risk increases.

## v2 capabilities

- **RoosterGuard** — every tool action is checked against an explicit permission and risk policy.
- **Permissions** — read, write, execute, network, and destructive capability classes.
- **Human approval gates** — medium/high/critical operations can require an explicit approval token.
- **Sandboxing** — file writes are restricted to `.rooster/sandbox`; path traversal is rejected.
- **Checkpoints** — recovery snapshots are created before engineering work and can be created manually.
- **Emergency stop** — immediately blocks guarded actions until the operator resets it.
- **Audit logging** — JSONL records task, authorization, approval, action, failure, checkpoint, and stop events.
- **Reason → Action → Evidence** — each task records why it is being done, what will be done, and what evidence should prove success.
- **Persistent task memory** — task state survives application restarts.
- **Desktop GUI** — live activity, task history, checkpoint control, and emergency-stop controls.

## Safety boundary

Rooster v2 does not silently grant itself network access, Git pushes, destructive deletion, or other high-impact capabilities. Those capabilities exist as explicit policy entries and require approval before execution. Self-modification of the guard should remain an operator-controlled change.

## Run

```powershell
python app.py
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Build Windows EXE

```powershell
.\build_windows.ps1
```

The existing build script produces `dist\Rooster Autonomous Engineer.exe`.
