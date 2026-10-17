$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$pythonExe = (Get-Command python).Source
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    $server = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'enterprise-server.out.log') -RedirectStandardError (Join-Path $runtimeDir 'enterprise-server.err.log')
    $server.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'enterprise-server.pid')
    Write-Output "Enterprise server started: PID $($server.Id), http://127.0.0.1:8000/enterprise"
} else { Write-Output 'Port 8000 already listening; existing process preserved.' }
$workerPidPath = Join-Path $runtimeDir 'enterprise-worker.pid'
$existingWorker = if (Test-Path -LiteralPath $workerPidPath) { Get-Process -Id ([int](Get-Content -LiteralPath $workerPidPath)) -ErrorAction SilentlyContinue }
if (-not $existingWorker) {
    $worker = Start-Process -FilePath $pythonExe -ArgumentList 'scripts/enterprise/run_enterprise_tasks.py','--watch' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'enterprise-worker.out.log') -RedirectStandardError (Join-Path $runtimeDir 'enterprise-worker.err.log')
    $worker.Id | Set-Content -LiteralPath $workerPidPath
    Write-Output "Enterprise worker started: PID $($worker.Id)"
}
