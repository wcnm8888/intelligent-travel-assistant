[CmdletBinding()]
param(
    [switch]$VersionParserSelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExpectedPython = "Python 3.13.3"
$ExpectedNode = "v22.16.0"
$ExpectedPnpm = "11.19.0"

function Invoke-NativeGate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

function Test-NativeVersionOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Output,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )

    $MatchingLines = @(
        $Output -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -eq $Expected }
    )
    return $MatchingLines.Count -eq 1
}

function Assert-NativeVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )

    $Output = (& $Command 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "$Name version check failed with exit code $LASTEXITCODE."
    }
    if (-not (Test-NativeVersionOutput $Output $Expected)) {
        throw "$Name version mismatch. Expected '$Expected', received '$Output'."
    }
    Write-Host "${Name}: $Expected" -ForegroundColor Green
}

if (-not (Test-NativeVersionOutput "Using managed runtime`n$ExpectedPython" $ExpectedPython)) {
    throw "Version parser self-test failed for diagnostic output."
}
if (Test-NativeVersionOutput "Python 3.12.0" $ExpectedPython) {
    throw "Version parser self-test accepted an incorrect version."
}
if (Test-NativeVersionOutput "$ExpectedPython`n$ExpectedPython" $ExpectedPython) {
    throw "Version parser self-test accepted duplicate version lines."
}
if ($VersionParserSelfTest) {
    Write-Host "Version parser self-test passed." -ForegroundColor Green
    exit 0
}

Push-Location $ProjectRoot
try {
    Write-Host "Intelligent Travel Assistant - local verification" -ForegroundColor White
    Write-Host "Project root: $ProjectRoot"

    Write-Host ""
    Write-Host "==> Runtime versions" -ForegroundColor Cyan
    Assert-NativeVersion "Python" {
        uv run --quiet --project backend --frozen python --version
    } $ExpectedPython
    Assert-NativeVersion "Node.js" { node --version } $ExpectedNode
    Assert-NativeVersion "pnpm" { corepack pnpm --version } $ExpectedPnpm

    Invoke-NativeGate "Backend lock validation" { uv lock --project backend --check }
    Invoke-NativeGate "Backend dependency sync" { uv sync --project backend --frozen }
    Invoke-NativeGate "Frontend frozen install" {
        corepack pnpm install --frozen-lockfile --ignore-scripts
    }
    Invoke-NativeGate "Frontend peer dependency validation" { corepack pnpm peers check }

    Invoke-NativeGate "Backend format check" {
        uv run --directory backend --frozen ruff format --check src tests ../scripts
    }
    Invoke-NativeGate "Backend lint" {
        uv run --directory backend --frozen ruff check src tests ../scripts
    }
    Invoke-NativeGate "Backend and script typecheck" {
        uv run --directory backend --frozen mypy src tests ../scripts
    }
    Invoke-NativeGate "Backend tests" { uv run --directory backend --frozen pytest }

    Invoke-NativeGate "Frontend format check" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend format:check
    }
    Invoke-NativeGate "CI workflow format check" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend exec prettier --check ../.github/workflows/ci.yml
    }
    Invoke-NativeGate "Frontend lint" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend lint
    }
    Invoke-NativeGate "Frontend typecheck" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend typecheck
    }
    Invoke-NativeGate "Frontend tests" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend test
    }
    Invoke-NativeGate "Frontend build" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend build
    }

    Invoke-NativeGate "Documentation checker tests" {
        uv run --project backend --frozen python -m unittest discover -s scripts/tests -p "test_*.py"
    }
    Invoke-NativeGate "Documentation and repository contracts" {
        uv run --project backend --frozen python scripts/check_docs.py --root .
    }

    Write-Host ""
    Write-Host "All local verification gates passed." -ForegroundColor Green
}
catch {
    Write-Error "Local verification failed: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
