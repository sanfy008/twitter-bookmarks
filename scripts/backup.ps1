$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $PSScriptRoot)

& uv run x-archive verify
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& uv run x-archive backup backups --keep 10
exit $LASTEXITCODE
