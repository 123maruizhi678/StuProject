$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
foreach ($item in @(@{File='enterprise-server.pid';Match='uvicorn app.main:app'},@{File='enterprise-worker.pid';Match='scripts/enterprise/run_enterprise_tasks.py'})) {
    $pidFile = Join-Path $projectRoot ('.runtime/' + $item.File)
    if (Test-Path -LiteralPath $pidFile) {
        $processId = [int](Get-Content -LiteralPath $pidFile)
        $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
        if ($ownedProcess -and $ownedProcess.CommandLine.Contains($item.Match)) {
            Stop-Process -Id $processId
            Write-Output "Stopped enterprise process $processId"
        }
    }
}
