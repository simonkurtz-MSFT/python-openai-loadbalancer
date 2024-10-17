Write-Host "`nSetting up the Python environment ...`n"

Write-Host "1) Creating Python virtual environment ...`n"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    # fallback to python3 if Python not found
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
Start-Process -FilePath ($pythonCmd).Source -ArgumentList "-m venv ./python_env" -Wait -NoNewWindow

$venvPythonPath = "./python_env/scripts/python.exe"
if (Test-Path -Path "/usr") {
    # fallback to Linux venv path
    $venvPythonPath = "./python_env/bin/python"
}

Write-Host "2) Restoring Python packages ...`n"

Start-Process -FilePath $venvPythonPath -ArgumentList "-m pip install -r requirements.txt" -Wait -NoNewWindow
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore Python packages"
    exit $LASTEXITCODE
}

Write-Host "`n`nDONE!`n"
