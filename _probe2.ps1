$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = "$root\.venv\Scripts\python.exe"
$p = Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8011') -WorkingDirectory $root -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 6
try {
    $s = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8011/api/sessions' -ContentType 'application/json' -Body '{"player_name":"阿梅"}'
    $body = '{"text":"/roll 2d6+1"}'
    $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8011/api/sessions/$($s.id)/command" -ContentType 'application/json' -Body $body
    "roll stats.rolls=$($r.session.stats.rolls) new_messages=$($r.new_messages.Count)"
    $cb = '{"text":"/check 侦查"}'
    $c = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8011/api/sessions/$($s.id)/command" -ContentType 'application/json' -Body $cb
    "check stats.checks=$($c.session.stats.checks)"
} finally {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}