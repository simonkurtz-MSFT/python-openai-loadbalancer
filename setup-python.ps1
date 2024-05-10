Write-Host "`nSetting up the python environment ...`n"

Write-Host "1) Creating python virtual environment ...`n"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    # fallback to python3 if python not found
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
Start-Process -FilePath ($pythonCmd).Source -ArgumentList "-m venv ./python_env" -Wait -NoNewWindow

$venvPythonPath = "./python_env/scripts/python.exe"
if (Test-Path -Path "/usr") {
    # fallback to Linux venv path
    $venvPythonPath = "./python_env/bin/python"
}

Write-Host "2) Restoring python packages ...`n"
 
Start-Process -FilePath $venvPythonPath -ArgumentList "-m pip install -r requirements.txt" -Wait -NoNewWindow
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore python packages"
    exit $LASTEXITCODE
}

Write-Host "`n`nDONE!`n"