param([Parameter(Mandatory)][string]$Source, [Parameter(Mandatory)][string]$Account,
      [Parameter(Mandatory)][ValidateSet("bookmark", "like")][string]$Type)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run x-archive import $Source --account $Account --type $Type
