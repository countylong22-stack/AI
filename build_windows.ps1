$ErrorActionPreference = "Stop"

Write-Host "Building Rooster Autonomous Engineer..." -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required. Install Python 3.11+ and rerun this script."
}

python -m pip install --upgrade pyinstaller

python -m PyInstaller --noconfirm --clean --windowed --name "Rooster Autonomous Engineer" --onefile app.py

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Executable: dist\Rooster Autonomous Engineer.exe"
