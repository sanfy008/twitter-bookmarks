param(
    [string]$Account = "",
    [string]$InboxDir = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not $InboxDir) {
    $InboxDir = Join-Path $ProjectRoot "inbox"
}
$ProcessedDir = Join-Path $InboxDir "processed"
$FailedDir = Join-Path $InboxDir "failed"
foreach ($dir in @($ProcessedDir, $FailedDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

$jsonFiles = @(Get-ChildItem -Path $InboxDir -Filter "*.json" -File |
    Where-Object { $_.DirectoryName -eq $InboxDir })

if ($jsonFiles.Count -eq 0) {
    Write-Host "[x-archive] No JSON files found in '$InboxDir'." -ForegroundColor Yellow
    Write-Host "[x-archive] Drop exported bookmark/like JSON files into 'inbox/' and re-run sync.ps1."
    exit 0
}

Write-Host "[x-archive] Found $($jsonFiles.Count) JSON file(s) in inbox." -ForegroundColor Cyan

$processedCount = 0
$failedCount = 0

foreach ($file in $jsonFiles) {
    $resolvedType = ""
    $resolvedAccount = $Account

    try {
        $json = Get-Content -Path $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($json.type -and ($json.type -in @("bookmark", "like"))) {
            $resolvedType = [string]$json.type
        }
        if ($json.account -and -not [string]::IsNullOrWhiteSpace([string]$json.account)) {
            $resolvedAccount = [string]$json.account
        }
    }
    catch {
        Write-Host "    WARN: could not parse metadata from '$($file.Name)': $($_.Exception.Message)" -ForegroundColor Yellow
    }

    if (-not $resolvedType) {
        if ($file.Name -match "(?i)likes?_") { $resolvedType = "like" }
        elseif ($file.Name -match "(?i)bookmarks?_") { $resolvedType = "bookmark" }
    }
    if (-not $resolvedAccount -and $file.Name -match "(?i)(?:bookmarks?|likes?)_([A-Za-z0-9_]+)_") {
        $resolvedAccount = $Matches[1]
    }
    if (-not $resolvedAccount) {
        $resolvedAccount = "owner"
    }
    if (-not $resolvedType) {
        Write-Host "    ERROR: cannot determine bookmark/like type for '$($file.Name)'." -ForegroundColor Red
        $failedCount++
        continue
    }

    Write-Host "--> Processing '$($file.Name)' (account: $resolvedAccount, type: $resolvedType)..." -ForegroundColor Cyan
    $output = & uv run x-archive import $file.FullName --account $resolvedAccount --type $resolvedType 2>&1
    $status = $LASTEXITCODE
    $output | Write-Host

    if ($status -eq 0) {
        $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
        $destination = Join-Path $ProcessedDir "$($file.BaseName)_$timestamp$($file.Extension)"
        Move-Item -Path $file.FullName -Destination $destination -Force
        $processedCount++
        Write-Host "    Archived file to '$destination'" -ForegroundColor Green
    }
    elseif ($status -eq 1) {
        # Record-level errors: valid rows were imported, but some rows were
        # rejected. Keep the source and an error report for manual review.
        $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
        $destination = Join-Path $FailedDir "$($file.BaseName)_$timestamp$($file.Extension)"
        Move-Item -Path $file.FullName -Destination $destination -Force
        $report = Join-Path $FailedDir "$($file.BaseName)_$timestamp.error.txt"
        $output | Out-String | Set-Content -Path $report -Encoding UTF8
        $failedCount++
        Write-Host "    Imported with record errors; moved to '$destination' and wrote '$report'." -ForegroundColor Yellow
    }
    else {
        Write-Host "    Import failed (exit code $status); leaving '$($file.Name)' in the inbox." -ForegroundColor Red
        $failedCount++
    }
}

if ($processedCount -gt 0) {
    Write-Host "`n[x-archive] Creating verified online backup..." -ForegroundColor Cyan
    & uv run x-archive backup backups --keep 10
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[x-archive] Backup failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    & uv run x-archive verify
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[x-archive] Verification failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[x-archive] Sync complete: $processedCount file(s) imported and verified." -ForegroundColor Green
}

if ($failedCount -gt 0) {
    Write-Host "[x-archive] $failedCount file(s) need attention (see inbox/failed)." -ForegroundColor Yellow
    exit 1
}
