param(
    [Parameter(Mandatory)][string]$Query,
    [int]$Limit = 20,
    [string]$Type = "",
    [string]$Account = "",
    [string]$Author = "",
    [string]$Since = "",
    [string]$Until = "",
    [switch]$HasMedia,
    [string]$Folder = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $PSScriptRoot)

if ($Type -and ($Type -notin @("bookmark", "like"))) {
    Write-Error "Type must be 'bookmark' or 'like'."
    exit 2
}

$arguments = @("run", "x-archive", "search", $Query, "--limit", $Limit)
if ($Type) { $arguments += @("--type", $Type) }
if ($Account) { $arguments += @("--account", $Account) }
if ($Author) { $arguments += @("--author", $Author) }
if ($Since) { $arguments += @("--since", $Since) }
if ($Until) { $arguments += @("--until", $Until) }
if ($HasMedia) { $arguments += "--has-media" }
if ($Folder) { $arguments += @("--folder", $Folder) }

& uv @arguments
exit $LASTEXITCODE
