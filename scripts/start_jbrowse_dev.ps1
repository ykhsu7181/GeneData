[CmdletBinding()]
param(
    [string]$WslDistribution = "Ubuntu",
    [int]$MySqlPort = 3306,
    [int]$MySqlBridgePort = 13306,
    [int]$DjangoPort = 2025,
    [int]$JBrowsePort = 18088,
    [int]$VuePort = 8080,
    [switch]$SkipNpmInstall
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeLogRoot = Join-Path $projectRoot ".runtime\jbrowse-dev\logs"
$processStatePath = Join-Path $projectRoot ".runtime\jbrowse-dev\processes.json"
New-Item -ItemType Directory -Force -Path $runtimeLogRoot | Out-Null

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is missing: $Name"
    }
}

function Assert-PortAvailable([int]$Port, [string]$Name) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $owners = @($listener.OwningProcess | Sort-Object -Unique) -join ","
        throw "$Name port $Port is already in use by PID $owners. Stop that service or choose another port."
    }
}

function Wait-Http([string]$Name, [string]$Uri, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "$Name ready: $Uri"
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)
    throw "$Name did not become ready within $TimeoutSeconds seconds. See $runtimeLogRoot"
}

Assert-Command "wsl.exe"
Assert-Command "node.exe"
Assert-Command "npm.cmd"
Assert-PortAvailable $MySqlBridgePort "MySQL bridge"
Assert-PortAvailable $DjangoPort "Django"
Assert-PortAvailable $JBrowsePort "JBrowse Nginx"
Assert-PortAvailable $VuePort "Vue"

if (-not $env:GENEDATA_DB_PASSWORD) {
    $credentialUser = if ($env:GENEDATA_DB_USER) { $env:GENEDATA_DB_USER } else { "root" }
    $credential = Get-Credential -UserName $credentialUser `
        -Message "Enter the local development MySQL password"
    $env:GENEDATA_DB_PASSWORD = $credential.GetNetworkCredential().Password
}
if (-not $env:GENEDATA_DB_USER) { $env:GENEDATA_DB_USER = "root" }
if (-not $env:GENEDATA_DB_NAME) { $env:GENEDATA_DB_NAME = "gene_manage" }

$projectRootForWsl = $projectRoot -replace '\\', '/'
$wslProjectRoot = (& wsl.exe -d $WslDistribution -- wslpath -a $projectRootForWsl).Trim()
if (-not $wslProjectRoot) { throw "Unable to resolve the repository path in WSL." }
$wslUser = (& wsl.exe -d $WslDistribution -- sh -lc 'printf "%s" "$USER"').Trim()
if (-not $wslUser) { throw "Unable to determine the WSL user." }
$wslRuntimeRoot = "/home/$wslUser/genedata-jbrowse-runtime"
$wslRuntimeScript = "$wslProjectRoot/scripts/jbrowse_dev_runtime.sh"

$defaultRoute = (& wsl.exe -d $WslDistribution -- ip route show default | Select-Object -First 1)
$routeFields = @($defaultRoute -split '\s+' | Where-Object { $_ })
if ($routeFields.Count -lt 3) { throw "Unable to determine the Windows host address from WSL." }
$windowsHostAddress = $routeFields[2]

Write-Host "Preparing the WSL JBrowse runtime..."
& wsl.exe -d $WslDistribution -- bash $wslRuntimeScript prepare $wslProjectRoot $wslRuntimeRoot $DjangoPort $JBrowsePort
if ($LASTEXITCODE -ne 0) { throw "WSL JBrowse preparation failed." }

$vueRoot = Join-Path $projectRoot "vue_project"
if (-not (Test-Path (Join-Path $vueRoot "node_modules"))) {
    if ($SkipNpmInstall) { throw "vue_project/node_modules is missing; rerun without -SkipNpmInstall." }
    Push-Location $vueRoot
    try { & npm.cmd ci } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
}

$bridgeProcess = $null
$djangoProcess = $null
$nginxProcess = $null
$vueProcess = $null
$oldWslEnv = $env:WSLENV
$oldJBrowseProxyTarget = $env:GENEDATA_JBROWSE_PROXY_TARGET
$oldDjangoProxyTarget = $env:GENEDATA_DJANGO_PROXY_TARGET

try {
    $bridgeArguments = @(
        (Join-Path $projectRoot "scripts\dev_mysql_bridge.mjs"),
        "--listen-address=$windowsHostAddress",
        "--listen-port=$MySqlBridgePort",
        "--target-address=127.0.0.1",
        "--target-port=$MySqlPort"
    )
    $bridgeProcess = Start-Process node.exe -ArgumentList $bridgeArguments -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeLogRoot "mysql-bridge.out.log") `
        -RedirectStandardError (Join-Path $runtimeLogRoot "mysql-bridge.err.log")

    $env:WSLENV = @(
        "GENEDATA_DB_PASSWORD/u",
        "GENEDATA_DB_USER/u",
        "GENEDATA_DB_NAME/u"
    ) -join ":"
    $env:GENEDATA_DB_HOST = $windowsHostAddress
    $env:GENEDATA_DB_PORT = [string]$MySqlBridgePort
    $env:WSLENV += ":GENEDATA_DB_HOST/u:GENEDATA_DB_PORT/u"

    $djangoProcess = Start-Process wsl.exe -ArgumentList @(
        "-d", $WslDistribution, "--", "bash", $wslRuntimeScript,
        "django", $wslProjectRoot, $wslRuntimeRoot, [string]$DjangoPort, [string]$JBrowsePort
    ) -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeLogRoot "django.out.log") `
        -RedirectStandardError (Join-Path $runtimeLogRoot "django.err.log")

    $nginxProcess = Start-Process wsl.exe -ArgumentList @(
        "-d", $WslDistribution, "--", "bash", $wslRuntimeScript,
        "nginx", $wslProjectRoot, $wslRuntimeRoot, [string]$DjangoPort, [string]$JBrowsePort
    ) -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeLogRoot "nginx.out.log") `
        -RedirectStandardError (Join-Path $runtimeLogRoot "nginx.err.log")

    $env:GENEDATA_JBROWSE_PROXY_TARGET = "http://localhost:$JBrowsePort"
    $env:GENEDATA_DJANGO_PROXY_TARGET = "http://localhost:$DjangoPort"
    $vueCli = Join-Path $vueRoot "node_modules\@vue\cli-service\bin\vue-cli-service.js"
    $vueProcess = Start-Process node.exe -WorkingDirectory $vueRoot -ArgumentList @(
        $vueCli, "serve", "--port", [string]$VuePort
    ) -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeLogRoot "vue.out.log") `
        -RedirectStandardError (Join-Path $runtimeLogRoot "vue.err.log")

    @{
        wsl_distribution = $WslDistribution
        wsl_project_root = $wslProjectRoot
        wsl_runtime_root = $wslRuntimeRoot
        django_port = $DjangoPort
        jbrowse_port = $JBrowsePort
        bridge_pid = $bridgeProcess.Id
        vue_pid = $vueProcess.Id
    } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $processStatePath

    Wait-Http "Django" "http://localhost:$DjangoPort/gd/api/files/assemblies/"
    Wait-Http "JBrowse" "http://localhost:$JBrowsePort/jbrowse2/"
    Wait-Http "Vue" "http://localhost:$VuePort/"

    Write-Host ""
    Write-Host "GeneData development environment is running."
    Write-Host "Portal:  http://localhost:$VuePort/"
    Write-Host "IR64 browser: http://localhost:$VuePort/assembly/131/browser"
    Write-Host "Logs:    $runtimeLogRoot"
    Write-Host "Press Ctrl+C to stop services started by this script."
    while ($true) {
        foreach ($service in @(
            @{ name = "MySQL bridge"; process = $bridgeProcess },
            @{ name = "Django"; process = $djangoProcess },
            @{ name = "Nginx"; process = $nginxProcess },
            @{ name = "Vue"; process = $vueProcess }
        )) {
            if ($service.process.HasExited) {
                throw "$($service.name) exited unexpectedly. See $runtimeLogRoot"
            }
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "Stopping GeneData development services..."
    try {
        & wsl.exe -d $WslDistribution -- bash $wslRuntimeScript stop $wslProjectRoot $wslRuntimeRoot $DjangoPort $JBrowsePort
    } catch {
        Write-Warning $_
    }
    foreach ($childProcess in @($vueProcess, $nginxProcess, $djangoProcess, $bridgeProcess)) {
        if ($childProcess -and -not $childProcess.HasExited) {
            Stop-Process -Id $childProcess.Id -ErrorAction SilentlyContinue
        }
    }
    $env:WSLENV = $oldWslEnv
    $env:GENEDATA_JBROWSE_PROXY_TARGET = $oldJBrowseProxyTarget
    $env:GENEDATA_DJANGO_PROXY_TARGET = $oldDjangoProxyTarget
    Remove-Item -LiteralPath $processStatePath -Force -ErrorAction SilentlyContinue
}
