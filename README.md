# Rooster Autonomous Engineer v1.2

## Downloadable Windows app

The repository now includes a Windows build script that packages Rooster as a standalone `.exe` using PyInstaller.

### Build the EXE

Open PowerShell in the repository folder and run:

```powershell
.\build_windows.ps1
```

The finished application will be created at:

```text
dist\Rooster Autonomous Engineer.exe
```

### Current features

- Desktop GUI
- Persistent task memory
- Autonomous engineering core
- Tool registry
- Workspace inspection
- Safe file reading
- Git status
- Task planning
- Background task execution
- Activity log
- Windows executable build

### Roadmap

1. Repository-aware code analysis
2. Structured edit plans
3. Test and build verification
4. Approval-gated file modifications
5. Git branch/commit workflow
6. LLM provider integration
7. One-click Windows release packaging
8. Installer and versioned releases
9. Optional web control plane
