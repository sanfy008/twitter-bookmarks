$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run pytest
uv run x-archive verify
