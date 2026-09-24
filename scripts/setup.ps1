$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv sync --dev
uv run x-archive init
uv run x-archive verify
