$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = "$root\.venv\Scripts\python.exe"

$p = Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8011') -WorkingDirectory $root -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 6
try {
    $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8011/api/health'
    "health: ok=$($h.ok) llm=$($h.llm_provider) image=$($h.image_provider) version=$($h.version)"
    $s = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8011/api/sessions' -ContentType 'application/json' -Body '{"player_name":"阿梅"}'
    "session: id=$($s.id) scene=$($s.state.scene_id) npcs=$($s.state.npcs.Count)"
    $b = Invoke-RestMethod -Uri 'http://127.0.0.1:8011/api/scenario/branches'
    "branches: nodes=$($b.nodes.Count) edges=$($b.edges.Count)"
    $r = Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8011/api/sessions/$($s.id)/command" -ContentType 'application/json' -Body '{"text":"/roll 2d6+1"}'
    "command /roll: $($r.StatusCode)"
    $home = Invoke-WebRequest -Uri 'http://127.0.0.1:8011/' 
    "index: $($home.StatusCode) bytes=$($home.RawContentLength)"
} finally {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}