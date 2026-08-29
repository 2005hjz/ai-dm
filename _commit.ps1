# ASCII-only helper: commit the engine repo.
$root = 'C:\Users\Lenovo\Desktop\ai-dm-engine'
Set-Location $root
Remove-Item -Force -ErrorAction SilentlyContinue _gate.ps1, _probe.ps1, _probe2.ps1, _behave.log, _commit.ps1
git init -b main | Out-Null
git add -A
git -c user.name='AI-DM Engine Team' -c user.email='team@ai-dm.engine' commit -m 'feat: AI DM engine - MVP core, multimodal providers, defensive programming, EDD eval, CI/Docker, full docs' 2>&1 | Select-Object -Last 2
git log --oneline -3