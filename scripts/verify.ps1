[CmdletBinding()]
param(
    [switch]$VersionParserSelfTest,
    [switch]$PythonVersionProbe,
    [ValidateSet('Development', 'ToolReadiness', 'FormalAcceptance', 'RepositoryVerification')]
    [string]$Phase = 'Development',
    [switch]$MechanismOnly,
    [switch]$GateSelfTest,
    [switch]$PreflightOnly,
    [string]$EvidenceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExpectedPython = "Python 3.13.3"
$ExpectedNode = "v22.16.0"
$ExpectedPnpm = "11.19.0"
$env:UV_BUILD_CONSTRAINT = Join-Path $ProjectRoot "backend\build-constraints.txt"

function Invoke-NativeGate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [ValidateSet('Static', 'MechanismTests', 'ProductTests')]
        [string]$Scope = 'Static'
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    # Windows PowerShell 5.1 can promote a native stderr progress line to a
    # terminating ErrorRecord when the global preference is Stop, even when
    # the native process exits zero. Capture it first, then apply this gate's
    # explicit exit-code and error-marker policy below.
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $RawOutput = @(& $Command 2>&1)
        $NativeExit = $LASTEXITCODE
        $Output = ($RawOutput | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $_.Exception.Message
            } else {
                [string]$_
            }
        } | Out-String)
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    $ExplicitError = $Output -match '(?im)### Error|TimeoutError|^\s*(error|fatal|exception|traceback)\b|os error \d+'
    $Failed = $NativeExit -ne 0 -or $ExplicitError
    # Keep locatable checker fields, never arbitrary output or assertion payloads.
    $Codes = @([regex]::Matches($Output, '(?m)^\s*([A-Z]{1,4}[0-9]{3,4})(?=\s|:)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique -First 10)
    $Tests = @([regex]::Matches($Output, '(?m)^(?:FAIL|ERROR): (test_[A-Za-z0-9_]+)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique -First 10)
    $Types = @([regex]::Matches($Output, '\b(?:AssertionError|AttributeError|TypeError|ValueError|FileNotFoundError|SyntaxError|TimeoutError)\b') | ForEach-Object { $_.Value } | Select-Object -Unique -First 10)
    $Locations = @([regex]::Matches($Output, '(?im)(?:^|[\\/])((?:scripts|backend|frontend)[\\/][A-Za-z0-9_. /\\-]+\.(?:py|ps1|tsx|ts))(?::([0-9]+))?') | ForEach-Object {
        $Relative = $_.Groups[1].Value.Replace('\', '/')
        $Resolved = [IO.Path]::GetFullPath((Join-Path $ProjectRoot $Relative))
        if ($Resolved.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $Resolved -PathType Leaf)) {
            [ordered]@{ path = $Relative; line = $_.Groups[2].Value }
        }
    } | Select-Object -First 10)
    $ProductResult = if ($Scope -eq 'ProductTests') { 'TESTS_EXECUTED_TERMINAL_NOT_CAPTURED' } else { 'NOT_APPLICABLE' }
    $Record = [ordered]@{
            phase = $Phase; command = $Name; exit_code = $NativeExit
            explicit_error = $ExplicitError; failed = $Failed
            scope = $Scope; synthetic = [bool]$GateSelfTest
            diagnostic_codes = $Codes; failed_tests = $Tests; error_types = $Types; locations = $Locations
            expected = 'exit zero and no explicit error'; actual = $(if ($Failed) { 'failed' } else { 'passed' })
            product_result = $ProductResult; request_id = 'NOT_CAPTURED'
            public_code = 'NOT_APPLICABLE'; diagnostic_code = 'NOT_APPLICABLE'
            http_status = 'NOT_APPLICABLE'; plan_id = 'NOT_APPLICABLE'; version = 'NOT_APPLICABLE'
            not_run = $(if ($Failed) { @('dependent gates') } else { @() })
    }
    $script:LastGateRecord = $Record
    if ($EvidenceDirectory) {
        $RecordPath = Join-Path $EvidenceDirectory (([guid]::NewGuid().ToString()) + '.json')
        $Record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $RecordPath -Encoding utf8
    }
    if ($Failed) {
        $Action = if ($Phase -eq 'FormalAcceptance') { 'FREEZE_ORIGINAL_BATCH' } else { 'REPAIR_WITHIN_AUTHORIZATION; check cumulative repair allowance in current-task' }
        Write-Host ($Record | ConvertTo-Json -Depth 5)
        throw "$Name failed (exit=$NativeExit, explicit_error=$ExplicitError); $Action. See structured diagnostic fields."
    }
    # Full product terminal objects must be captured by the corresponding journey probe.
    Write-Host "$Name passed." -ForegroundColor Green
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
if ($PythonVersionProbe) {
    Push-Location $ProjectRoot
    try {
    Assert-NativeVersion "Python" {
        uv run --quiet --project backend --frozen python --version
    } $ExpectedPython
    } finally { Pop-Location }
    exit 0
}

Push-Location $ProjectRoot
try {
    if ($EvidenceDirectory) {
        $EvidenceDirectory = [IO.Path]::GetFullPath((Join-Path $ProjectRoot $EvidenceDirectory))
        $AllowedRoot = (Join-Path $ProjectRoot 'output\diagnostics') + [IO.Path]::DirectorySeparatorChar
        if (-not $EvidenceDirectory.StartsWith($AllowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'EvidenceDirectory must stay inside project output/diagnostics.'
        }
        if (Test-Path -LiteralPath $EvidenceDirectory) { throw 'EvidenceDirectory must be new.' }
        New-Item -ItemType Directory -Path $EvidenceDirectory | Out-Null
    }
    if ($GateSelfTest) {
        foreach ($Case in @('nonzero', 'zero-error', 'zero-timeout', 'diagnostic')) {
            $Detected = $false
            try {
                Invoke-NativeGate -Name "synthetic-$Case" -Scope ProductTests -Command {
                    if ($Case -eq 'nonzero') { & $env:ComSpec /d /c 'exit /b 7' }
                    elseif ($Case -eq 'zero-error') { & $env:ComSpec /d /c 'echo ### Error synthetic& exit /b 0' }
                    elseif ($Case -eq 'zero-timeout') { & $env:ComSpec /d /c 'echo TimeoutError synthetic& exit /b 0' }
                    else { & $env:ComSpec /d /c 'echo FAIL: test_synthetic_recovery (synthetic)& echo scripts/check_f008_readiness.py:45: E501& echo E501 Line too long& echo AssertionError: synthetic-private-value-never-persist& exit /b 1' }
                }
            } catch {
                $ExpectedAction = if ($Phase -eq 'FormalAcceptance') { 'FREEZE_ORIGINAL_BATCH' } else { 'REPAIR_WITHIN_AUTHORIZATION' }
                if ($_.Exception.Message -notmatch $ExpectedAction) { throw }
                $Detected = $true
            }
            if (-not $Detected) { throw "Guard did not detect $Case." }
            if ($Case -eq 'diagnostic') {
                $Serialized = $script:LastGateRecord | ConvertTo-Json -Depth 5
                if ($Serialized -match 'synthetic-private-value-never-persist' -or
                    $script:LastGateRecord.failed_tests -notcontains 'test_synthetic_recovery' -or
                    $script:LastGateRecord.diagnostic_codes -notcontains 'E501' -or
                    $script:LastGateRecord.locations.Count -eq 0 -or
                    $script:LastGateRecord.product_result -ne 'TESTS_EXECUTED_TERMINAL_NOT_CAPTURED') {
                    throw 'Synthetic diagnostic retention/redaction self-test failed.'
                }
            }
        }
        Invoke-NativeGate 'synthetic-benign-stderr' {
            & $env:ComSpec /d /c 'echo benign progress 1>&2& exit /b 0'
        }
        Invoke-NativeGate 'synthetic-success' { & $env:ComSpec /d /c 'echo ok& exit /b 0' }
        Write-Host 'Native gate self-test PASS (synthetic only; no formal batch).'
        exit 0
    }
    if ($MechanismOnly -and $Phase -eq 'RepositoryVerification') {
        throw 'RepositoryVerification requires all quality gates.'
    }
    if ($MechanismOnly) {
        $Targets = @('../scripts/check_docs.py', '../scripts/check_current_task_readiness.py', '../scripts/check_f008_readiness.py', '../scripts/tests/test_check_docs.py', '../scripts/tests/test_check_current_task_readiness.py', '../scripts/tests/test_check_f008_readiness.py')
        Invoke-NativeGate 'Mechanism format' { uv run --offline --no-sync --directory backend ruff format --check @Targets }
        Invoke-NativeGate 'Mechanism lint' { uv run --offline --no-sync --directory backend ruff check @Targets }
        Invoke-NativeGate 'Mechanism strict types' { uv run --offline --no-sync --directory backend mypy --strict --no-incremental @Targets }
        Invoke-NativeGate -Name 'Mechanism unit tests' -Scope MechanismTests -Command {
            uv run --offline --no-sync --directory backend python -B -m unittest discover -s ../scripts/tests -p 'test_*.py'
        }
        Invoke-NativeGate -Name 'Capture unit tests' -Scope MechanismTests -Command {
            node --test scripts/tests/test_capture_f008_replan.js
        }
        Invoke-NativeGate 'Documentation contracts' {
            uv run --offline --no-sync --directory backend python -B ../scripts/check_docs.py --root ..
        }
        exit 0
    }
    # Repository verification exercises all quality gates without opening a task or UAT batch.
    if ($Phase -eq 'RepositoryVerification') {
        if ($PreflightOnly) { throw 'RepositoryVerification requires all quality gates.' }
    } else {
        $PhaseName = @{Development='development'; ToolReadiness='tool_readiness'; FormalAcceptance='formal_acceptance'}[$Phase]
        & uv run --offline --no-sync --directory backend python -B ../scripts/check_current_task_readiness.py --root $ProjectRoot --phase $PhaseName
        if ($LASTEXITCODE -ne 0) { throw 'Preflight refused before product gates; no formal batch created.' }
        if ($PreflightOnly -or $Phase -eq 'ToolReadiness') { exit 0 }
    }
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
    # Browser boundary tests mount the built frontend, including on a clean checkout.
    Invoke-NativeGate "Frontend build" {
        corepack pnpm --filter @intelligent-travel-assistant/frontend build
    }
    Invoke-NativeGate -Name 'Backend tests' -Scope ProductTests -Command { uv run --directory backend --frozen pytest }

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
    Invoke-NativeGate -Name 'Frontend tests' -Scope ProductTests -Command {
        corepack pnpm --filter @intelligent-travel-assistant/frontend test
    }

    Invoke-NativeGate "Documentation checker tests" {
        $PreviousAppEnv = $env:APP_ENV
        $env:APP_ENV = 'test'
        try {
            uv run --directory backend --frozen python -m unittest discover -s ../scripts/tests -p "test_*.py"
        } finally {
            if ($null -eq $PreviousAppEnv) { Remove-Item Env:APP_ENV -ErrorAction SilentlyContinue }
            else { $env:APP_ENV = $PreviousAppEnv }
        }
    }
    Invoke-NativeGate -Name 'Capture unit tests' -Scope MechanismTests -Command {
        node --test scripts/tests/test_capture_f008_replan.js
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
