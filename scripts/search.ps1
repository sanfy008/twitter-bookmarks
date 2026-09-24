param([Parameter(Mandatory)][string]$Query, [int]$Limit = 20)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run x-archive search $Query --limit $Limit
