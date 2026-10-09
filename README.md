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
- **Android mobile companion** — an Android app can connect to the Rooster computer for status and emergency-stop control.

## Rooster Pentester

The `rooster_pentester/` package provides an authorization-first security assessment toolkit alongside Rooster Autonomous Engineer v2:

- **Local computer audit:** read-only OS, TCP listener, Windows Firewall, and Defender checks where available, gated by user confirmation and RoosterGuard approval.
- **Web security review:** exact-host allowlisting, common security-header checks, and redirects that are reported but never followed automatically.
- **Network checks:** explicit CIDR allowlisting and small, rate-limited TCP connection checks.
- **Reports:** portable JSON and self-contained HTML reports with evidence, remediation guidance, severity summaries, and an explicitly heuristic triage score.
- **Audit integrity:** hash-chained JSONL events, full-chain integrity verification, and refusal to append to a tampered log.
- **Cross-platform CI:** Python compilation and unit tests on Windows and Ubuntu.

For the local workflow, click **PENTEST MY COMPUTER**, confirm local-only scope, review the proposed action, and click **APPROVE ACTION**. After completion, click **Open Pentest Report**. Reports are saved under `.rooster/pentester-reports/`; audit events are saved to `.rooster/pentester-audit.jsonl`.

See [Rooster Pentester documentation](docs/ROOSTER_PENTESTER.md). Only assess systems you own or have explicit written permission to test. This is a low-impact assessment foundation, not a full penetration test or proof that a system is secure. It does not include exploit payloads, credential attacks, stealth, persistence, or automatic remediation.

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
.\\build_windows.ps1
```

The build produces `dist\\Rooster Autonomous Engineer.exe`.

## Android mobile companion

The Android project is under `mobile/`. The companion currently provides:

- Rooster computer connection settings
- authenticated status checking
- emergency stop
- emergency-stop reset

The phone app intentionally does **not** expose arbitrary engineering execution. Engineering work remains on the Rooster computer behind RoosterGuard.

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
