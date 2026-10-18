$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sessionPath = Join-Path $projectRoot '.runtime/dev-session.json'
if (-not (Test-Path -LiteralPath $sessionPath)) { Write-Output '没有本项目启动记录。'; exit 0 }
$session = Get-Content -LiteralPath $sessionPath -Raw | ConvertFrom-Json
foreach ($service in $session.children) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($service.pid)" -ErrorAction SilentlyContinue
    $expectedArguments = $service.args -join ' '
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($expectedArguments)) {
        Stop-Process -Id $service.pid -ErrorAction SilentlyContinue
    }
}
$supervisor = Get-CimInstance Win32_Process -Filter "ProcessId=$($session.pid)" -ErrorAction SilentlyContinue
if ($supervisor -and $supervisor.CommandLine -like '*scripts/dev.mjs*') {
    Stop-Process -Id $session.pid -ErrorAction SilentlyContinue
}
Write-Output '本次启动的前后端及通知任务已停止；复用的既有后端未停止。'
