param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$Account,
    [Parameter(Mandatory)][ValidateSet("bookmark", "like")][string]$Type
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $PSScriptRoot)

& uv run x-archive import $Source --account $Account --type $Type
exit $LASTEXITCODE
