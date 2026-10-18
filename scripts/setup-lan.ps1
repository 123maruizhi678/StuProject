$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$resultPath = Join-Path $projectRoot '.runtime/lan-setup-result.json'
$serverAddress = '192.168.5.12'
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script in an Administrator PowerShell window.'
    }
    if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $serverAddress)) {
        throw 'This server does not have IPv4 address 192.168.5.12.'
    }
    $ruleName = 'StuProject-HTTP-LAN-80'
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($rule) {
        Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Any -Protocol TCP -LocalPort 80 -LocalAddress $serverAddress -RemoteAddress LocalSubnet | Out-Null
    } else {
        New-NetFirewallRule -Name $ruleName -DisplayName 'StuProject HTTP LAN 80' -Enabled True -Direction Inbound -Action Allow -Profile Any -Protocol TCP -LocalPort 80 -LocalAddress $serverAddress -RemoteAddress LocalSubnet | Out-Null
    }
    # Remove only the exact entry created by the superseded local-domain setup.
    # Latin-1 round-tripping preserves every other byte of the existing hosts file.
    $hostsPath = Join-Path $env:SystemRoot 'System32/drivers/etc/hosts'
    $byteEncoding = [Text.Encoding]::GetEncoding(28591)
    $hostsContent = $byteEncoding.GetString([IO.File]::ReadAllBytes($hostsPath))
    $cleanHosts = [regex]::Replace($hostsContent, '(?m)^192\.168\.5\.12\tlogin\.html\t# StuProject LAN\r?\n?', '')
    if ($cleanHosts -ne $hostsContent) {
        [IO.File]::WriteAllBytes($hostsPath, $byteEncoding.GetBytes($cleanHosts))
        Clear-DnsClientCache
    }
    $result = @{ success = $true; url = 'http://192.168.5.12/login.html'; server = $serverAddress; firewall = $true }
    New-Item -ItemType Directory -Force -Path (Split-Path $resultPath) | Out-Null
    $result | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Output 'Configured LAN HTTP access: http://192.168.5.12/login.html. No hosts or DNS configuration required.'
} catch {
    $result = @{ success = $false; error = $_.Exception.Message }
    New-Item -ItemType Directory -Force -Path (Split-Path $resultPath) | Out-Null
    $result | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Error $_.Exception.Message
    exit 1
}
