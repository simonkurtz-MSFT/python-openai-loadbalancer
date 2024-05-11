# This is the original work that targeted only a single python worker (no parallelism). This is an unlikely scenario for production, but I decided to keep it in the repo.

Write-Host "`nExecuting python Azure OpenAI ...`n"

$venvPythonPath = "./python_env/scripts/python.exe"
if (Test-Path -Path "/usr") {
    # fallback to Linux venv path
    $venvPythonPath = "./python_env/bin/python"
}

Start-Process -FilePath $venvPythonPath -ArgumentList "./aoai-single-requestor.py" -Wait -NoNewWindow
