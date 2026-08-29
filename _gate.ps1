$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
Write-Output '== ruff =='
& "$PSScriptRoot\.venv\Scripts\ruff.exe" check app tests eval 2>&1 | Select-Object -Last 2
Write-Output '== pytest =='
& "$PSScriptRoot\.venv\Scripts\python.exe" -m pytest tests -q --no-cov 2>&1 | Select-Object -Last 2
Write-Output '== behave =='
& "$PSScriptRoot\.venv\Scripts\behave.exe" "$PSScriptRoot\tests\bdd\features" 2>&1 | Select-Object -Last 2
Write-Output '== eval =='
& "$PSScriptRoot\.venv\Scripts\python.exe" -X utf8 "$PSScriptRoot\eval\score.py" 2>&1 | Select-Object -First 1