$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $PSScriptRoot)

& uv run ruff check .
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& uv run ruff format --check .
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& uv run pytest
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (Get-Command node -ErrorAction SilentlyContinue) {
    & node scripts/check-userscript.mjs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
else {
    Write-Host "[x-archive] node not found; skipping userscript behaviour checks." -ForegroundColor Yellow
}

& uv run x-archive verify
exit $LASTEXITCODE
