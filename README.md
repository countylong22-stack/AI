# Rooster Autonomous Engineer v2

Rooster v2 is a guarded autonomous engineering workspace for Windows and Python. It adds a policy boundary between the agent and its tools so autonomy is observable, interruptible, and approval-gated where risk increases.

## Proprietary licensing

Rooster Autonomous Engineer is intended to be distributed as proprietary software. Unless a separate written license signed by the rights holder says otherwise, no permission is granted to copy, modify, redistribute, sublicense, or sell this source code or derivative works. Access to a repository or download is not itself a commercial license.

For paid use, redistribution, source-code access, or business deployment, obtain a written commercial license from the rights holder first. This notice is not a payment processor or access-control mechanism. Keep the GitHub repository private and distribute builds only through a controlled customer channel. Code already cloned, forked, or downloaded while the repository was public cannot reliably be recalled by changing visibility. This notice is a starting point, not legal advice; have a qualified attorney review the commercial terms before selling licenses.

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
- **Engineering-only interface** — the desktop app exposes guarded autonomous engineering, workspace inspection, task history, verification, and emergency-stop controls. Video editing and media-generation actions are not part of the app or tool registry.
- **Windows app build** — GitHub Actions automatically builds a standalone `Rooster Autonomous Engineer.exe` for Windows.
- **Android mobile companion** — authenticated chat, voice input/output, PC status, autonomous task submission/progress, and emergency-stop control.

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

The build produces `dist\Rooster Autonomous Engineer.exe`.

## Android mobile companion

The Android project is under `mobile/`. The companion provides chat, speech-to-text, spoken replies, authenticated PC status, autonomous task submission/progress, and emergency stop/reset. Engineering work runs on the Rooster computer through the guarded agent; ordinary chat alone does not execute tasks.

### Agent model and autonomy settings

The autonomous coding agent defaults to the documented `gpt-6.1-sol` model with high reasoning effort. Mobile chat uses the Responses API with `gpt-6.1-sol` and medium reasoning effort. These are configurable with environment variables:

- `ROOSTER_AGENT_MODEL` — coding-agent model ID
- `ROOSTER_REASONING_EFFORT` — coding reasoning effort: `low`, `medium`, `high`, `xhigh`, or `max`
- `ROOSTER_CHAT_MODEL` — mobile-chat model ID
- `ROOSTER_CHAT_REASONING_EFFORT` — mobile-chat reasoning effort
- `ROOSTER_MAX_ITERATIONS` — autonomous coding iterations, 1–10 (default 5)

The agent carries recent test evidence into later attempts and makes one formatting-repair retry for invalid JSON. Increasing iteration or reasoning settings can increase runtime and API cost. Rooster still keeps checkpoints, audit logs, protected security code, bounded file changes, and the emergency stop.

### Build the APK

GitHub Actions automatically builds a debug APK on pushes to `v2/rooster-guard`. The artifact is named **Rooster-Autonomous-Engineer-Android**.

To run the companion API on the Rooster computer:

```powershell
python -m pip install -r requirements.txt
$env:ROOSTER_API_TOKEN = "choose-a-long-random-token"
python mobile_server.py --host 0.0.0.0 --port 8765
```

Then enter the computer's LAN address and the same token in the Android app. Keep the API on a trusted network and use a firewall rule/VPN rather than exposing port 8765 directly to the public internet.

## Download the Windows app from GitHub Actions

Every push to `v2/rooster-guard` also runs the Windows app build. When the build succeeds, open the workflow run in GitHub and download the artifact named **Rooster-Autonomous-Engineer-Windows**. It contains the standalone Windows EXE, so Python is not required on the target PC.

Android CI note: the APK workflow uses the runner's Android SDK directly and installs only the stable platform/build-tools needed for this project.
