[CmdletBinding()]
param(
    [string]$Commit = "HEAD",
    [string]$ReleaseDate = "20261009",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $projectRoot ".artifacts\releases"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$resolvedCommit = (& git -C $projectRoot rev-parse "$Commit^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or -not $resolvedCommit) {
    throw "Unable to resolve commit: $Commit"
}
$headCommit = (& git -C $projectRoot rev-parse HEAD).Trim()
if ($resolvedCommit -ne $headCommit) {
    throw "Build only the checked-out HEAD commit."
}
& git -C $projectRoot diff --quiet --exit-code
if ($LASTEXITCODE -ne 0) { throw "Tracked working-tree changes exist." }
& git -C $projectRoot diff --cached --quiet --exit-code
if ($LASTEXITCODE -ne 0) { throw "Staged changes exist." }

$shortCommit = $resolvedCommit.Substring(0, 7)
$releaseName = "GeneData_JBrowse_alias_${shortCommit}_${ReleaseDate}"
$releaseDirectory = Join-Path $OutputRoot $releaseName
$archivePath = Join-Path $OutputRoot "$releaseName.zip"
$archiveChecksumPath = "$archivePath.sha256"
$sourceArchive = Join-Path $OutputRoot ".$releaseName.source.zip"
foreach ($path in @($releaseDirectory, $archivePath, $archiveChecksumPath, $sourceArchive)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing release path: $path"
    }
}

$runbooks = @(
    Get-ChildItem -LiteralPath (Join-Path $projectRoot "docs") -File |
        Where-Object { $_.Name -like "GeneData_JBrowse_OriSeqID_hotfix_*_20261009.md" }
)
if ($runbooks.Count -ne 1) {
    throw "Expected exactly one OriSeqID hotfix runbook; found $($runbooks.Count)."
}
$runbookPath = $runbooks[0].FullName

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
try {
    & git -C $projectRoot archive --format=zip --output=$sourceArchive $resolvedCommit -- django2
    if ($LASTEXITCODE -ne 0) { throw "git archive failed." }
    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $releaseDirectory
    New-Item -ItemType Directory -Path (Join-Path $releaseDirectory "docs") | Out-Null
    Copy-Item -LiteralPath $runbookPath -Destination (
        Join-Path $releaseDirectory "docs/PRODUCTION_DEPLOYMENT_RUNBOOK.md"
    )

    $info = @(
        "release_name=$releaseName"
        "source_commit=$resolvedCommit"
        "production_baseline=b0a1ce8"
        "scope=django2-only OriSeqID JBrowse index hotfix"
        "unchanged=dist,jbrowse2-v4.3.0,nginx,manual_files,database_schema"
        "excludes=secrets,manual_files,derived_data,database,logs,venv,node_modules,runtime"
    ) -join "`n"
    [System.IO.File]::WriteAllText(
        (Join-Path $releaseDirectory "RELEASE_INFO.txt"),
        "$info`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $checksumPath = Join-Path $releaseDirectory "SHA256SUMS"
    $lines = Get-ChildItem -LiteralPath $releaseDirectory -Recurse -File |
        Where-Object { $_.FullName -ne $checksumPath } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($releaseDirectory.Length + 1).Replace('\', '/')
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            "$hash  $relative"
        }
    [System.IO.File]::WriteAllText(
        $checksumPath,
        (($lines -join "`n") + "`n"),
        [System.Text.Encoding]::ASCII
    )

    Compress-Archive -LiteralPath $releaseDirectory -DestinationPath $archivePath -CompressionLevel Optimal
    $archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        $archiveChecksumPath,
        "$archiveHash  $releaseName.zip`n",
        [System.Text.Encoding]::ASCII
    )
} finally {
    Remove-Item -LiteralPath $sourceArchive -Force -ErrorAction SilentlyContinue
}

Write-Host "Release directory: $releaseDirectory"
Write-Host "Archive: $archivePath"
Write-Host "Checksum: $archiveChecksumPath"
Write-Host "Source commit: $resolvedCommit"
