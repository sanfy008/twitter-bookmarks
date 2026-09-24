$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run x-archive verify
uv run x-archive backup backups
