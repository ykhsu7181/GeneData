[CmdletBinding()]
param(
    [string]$Commit = "b0a1ce8",
    [string]$ReleaseDate = "20260929",
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
& git -C $projectRoot merge-base --is-ancestor $resolvedCommit $headCommit
if ($LASTEXITCODE -ne 0) {
    throw "Release commit ($resolvedCommit) is not an ancestor of HEAD ($headCommit)."
}
& git -C $projectRoot diff --quiet --exit-code
if ($LASTEXITCODE -ne 0) {
    throw "Tracked working-tree changes exist. Commit or restore them before packaging."
}
& git -C $projectRoot diff --cached --quiet --exit-code
if ($LASTEXITCODE -ne 0) {
    throw "Staged changes exist. Commit or unstage them before packaging."
}

$shortCommit = $resolvedCommit.Substring(0, 7)
$releaseName = "GeneData_${shortCommit}_${ReleaseDate}"
$releaseDirectory = Join-Path $OutputRoot $releaseName
$archivePath = Join-Path $OutputRoot "$releaseName.zip"
$archiveChecksumPath = "$archivePath.sha256"
$sourceArchive = Join-Path $OutputRoot ".$releaseName.source.zip"

foreach ($path in @($releaseDirectory, $archivePath, $archiveChecksumPath, $sourceArchive)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing release path: $path"
    }
}

$distRoot = Join-Path $projectRoot "vue_project\dist"
$jbrowseRoot = Join-Path $projectRoot "tmp\jbrowse2-web-v4.3.0"
$runbookMatches = @(
    Get-ChildItem -LiteralPath (Join-Path $projectRoot "docs") -File |
        Where-Object { $_.Name -like "*JBrowse2*b0a1ce8.md" }
)
if ($runbookMatches.Count -ne 1) {
    throw "Expected exactly one JBrowse2 b0a1ce8 deployment runbook; found $($runbookMatches.Count)."
}
$runbookPath = $runbookMatches[0].FullName
foreach ($requiredPath in @(
    (Join-Path $distRoot "index.html"),
    (Join-Path $jbrowseRoot "index.html"),
    (Join-Path $jbrowseRoot "version.txt"),
    $runbookPath
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required release input is missing: $requiredPath"
    }
}
$jbrowseVersion = (Get-Content -Raw -LiteralPath (Join-Path $jbrowseRoot "version.txt")).Trim()
if ($jbrowseVersion -ne "4.3.0") {
    throw "Expected JBrowse Web 4.3.0, found: $jbrowseVersion"
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
try {
    & git -C $projectRoot archive --format=zip --output=$sourceArchive $resolvedCommit -- `
        django2 `
        deploy/nginx/genedata-jbrowse2.conf.example `
        scripts/build_jbrowse2_web.sh `
        .env.example
    if ($LASTEXITCODE -ne 0) { throw "git archive failed." }

    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $releaseDirectory
    Copy-Item -Recurse -LiteralPath $distRoot -Destination (Join-Path $releaseDirectory "dist")
    $jbrowseReleaseDirectory = Join-Path $releaseDirectory "jbrowse2-v4.3.0"
    New-Item -ItemType Directory -Path $jbrowseReleaseDirectory | Out-Null
    Get-ChildItem -LiteralPath $jbrowseRoot |
        Where-Object { $_.Name -ne "test_data" } |
        ForEach-Object {
            Copy-Item -Recurse -LiteralPath $_.FullName -Destination $jbrowseReleaseDirectory
        }
    New-Item -ItemType Directory -Force -Path (Join-Path $releaseDirectory "docs") | Out-Null
    Copy-Item -LiteralPath $runbookPath -Destination (
        Join-Path $releaseDirectory "docs\PRODUCTION_DEPLOYMENT_RUNBOOK_b0a1ce8.md"
    )

    $branch = (& git -C $projectRoot branch --show-current).Trim()
    $commitSubject = (& git -C $projectRoot log -1 --format=%s $resolvedCommit).Trim()
    $commitTime = (& git -C $projectRoot log -1 --format=%cI $resolvedCommit).Trim()
    $packagingCommit = $headCommit
    $buildTime = [DateTimeOffset]::UtcNow.ToString("o")
    @(
        "release_name=$releaseName"
        "source_commit=$resolvedCommit"
        "packaging_commit=$packagingCommit"
        "source_branch=$branch"
        "commit_subject=$commitSubject"
        "commit_time=$commitTime"
        "build_time_utc=$buildTime"
        "jbrowse_web_version=$jbrowseVersion"
        "production_baseline=557aa17"
        "contains=django2,dist,jbrowse2-v4.3.0,nginx-example,build-script,runbook"
        "excludes=secrets,manual_files,derived_data,database,logs,venv,node_modules,runtime,jbrowse_upstream_test_data"
    ) | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $releaseDirectory "RELEASE_INFO.txt")

    $checksumPath = Join-Path $releaseDirectory "SHA256SUMS"
    $checksumLines = Get-ChildItem -LiteralPath $releaseDirectory -Recurse -File |
        Where-Object { $_.FullName -ne $checksumPath } |
        Sort-Object FullName |
        ForEach-Object {
            $relativePath = $_.FullName.Substring($releaseDirectory.Length + 1).Replace('\', '/')
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            "$hash  $relativePath"
        }
    $checksumLines | Set-Content -Encoding ASCII -LiteralPath $checksumPath

    Compress-Archive -LiteralPath $releaseDirectory -DestinationPath $archivePath -CompressionLevel Optimal
    $archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    "$archiveHash  $releaseName.zip" | Set-Content -Encoding ASCII -LiteralPath $archiveChecksumPath
} finally {
    Remove-Item -Force -LiteralPath $sourceArchive -ErrorAction SilentlyContinue
}

Write-Host "Release directory: $releaseDirectory"
Write-Host "Release archive:   $archivePath"
Write-Host "Archive checksum:  $archiveChecksumPath"
Write-Host "Source commit:     $resolvedCommit"
