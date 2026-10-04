# Rooster Autonomous Engineer v2

Rooster v2 is a guarded autonomous engineering workspace for Windows and Python. It adds a policy boundary between the agent and its tools so autonomy is observable, interruptible, and approval-gated where risk increases.

## v2 capabilities

- **RoosterGuard** — every tool action is checked against an explicit permission and risk policy.
- **Permissions** — read, write, execute, network, and destructive capability classes.
- **Human approval gates** — approval is tied to the exact action, expires after a short window, and is consumed after one authorization.
- **Sandboxing** — automated file writes are restricted to `.rooster/sandbox`; path traversal and symlink escapes are rejected.
- **Checkpoints** — recovery snapshots are created before engineering work; Git metadata and Rooster runtime state are excluded and symlinks are preserved.
- **Emergency stop** — immediately blocks guarded actions until the operator explicitly resets it.
- **Audit logging** — JSONL records task, authorization, approval, action, failure, checkpoint, and stop events using a hash chain.
- **Reason → Action → Evidence** — each task records why it is being done, what will be done, and what evidence should prove success.
- **Persistent task memory** — task state survives application restarts with atomic replacement.
- **Desktop GUI** — live activity, task history, checkpoint control, and emergency-stop controls.
- **Windows app build** — GitHub Actions automatically builds a standalone `Rooster Autonomous Engineer.exe` for Windows.

## Safety boundary

Rooster v2 does not silently grant itself network access, Git pushes, destructive deletion, arbitrary shell execution, or other high-impact capabilities. Those capabilities require explicit policy entries and, where configured, human approval. The safety boundary itself should remain an operator-controlled repository change.

See `SECURITY.md` for the security boundary and future command/network requirements.

## Run from Python

```powershell
python app.py
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Build Windows EXE locally

```powershell
.\build_windows.ps1
```

The build produces:

```text
dist\Rooster Autonomous Engineer.exe
```

## Download the Windows app from GitHub Actions

Every push to `v2/rooster-guard` also runs the Windows app build. When the build succeeds, open the workflow run in GitHub and download the artifact named **Rooster-Autonomous-Engineer-Windows**. It contains the standalone Windows EXE, so Python is not required on the target PC.
