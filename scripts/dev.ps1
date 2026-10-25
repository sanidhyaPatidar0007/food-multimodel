# Run backend and frontend together (Windows PowerShell). Close the spawned window to stop the backend.
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Set-Location "$root\frontend"; npm run dev
