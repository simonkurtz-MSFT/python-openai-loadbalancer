Write-Host "`nExecuting python Azure OpenAI ...`n"

$venvPythonPath = "./python_env/scripts/python.exe"
if (Test-Path -Path "/usr") {
    # fallback to Linux venv path
    $venvPythonPath = "./python_env/bin/python"
}
 
Start-Process -FilePath $venvPythonPath -ArgumentList "./aoai-single-requestor.py" -Wait -NoNewWindow