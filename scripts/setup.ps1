$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $PSScriptRoot)

& uv sync --dev
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& uv run x-archive init
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& uv run x-archive verify
exit $LASTEXITCODE
