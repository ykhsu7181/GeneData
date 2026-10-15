[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $projectRoot ".runtime\jbrowse-dev\processes.json"

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host "No JBrowse development process state was found."
    exit 0
}

$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
$runtimeScript = "$($state.wsl_project_root)/scripts/jbrowse_dev_runtime.sh"

& wsl.exe -d $state.wsl_distribution -- bash $runtimeScript stop `
    $state.wsl_project_root $state.wsl_runtime_root `
    ([string]$state.django_port) ([string]$state.jbrowse_port)

foreach ($entry in @(
    @{ pid = [int]$state.vue_pid; marker = "vue-cli-service.js" },
    @{ pid = [int]$state.bridge_pid; marker = "dev_mysql_bridge.mjs" }
)) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.pid)" -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    if ($process.CommandLine -notlike "*$($entry.marker)*") {
        Write-Warning "Refusing to stop PID $($entry.pid): command line does not match $($entry.marker)."
        continue
    }
    Stop-Process -Id $entry.pid -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $statePath -Force
Write-Host "JBrowse development services started by the launcher have been stopped."
