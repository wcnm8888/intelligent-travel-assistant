[CmdletBinding()]
param(
    [switch]$ContractSelfTest,
    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExpectedPython = "3.13.3"
$ExpectedNode = "22.16.0"
$ExpectedPnpm = "11.19.0"
$BackendPort = 8000
$FrontendPort = 5173
$BackendHealthUri = "http://127.0.0.1:8000/api/health"
$FrontendUri = "http://127.0.0.1:5173/"
$StartupTimeoutSeconds = 30

$env:COREPACK_ENABLE_NETWORK = "0"
$env:UV_OFFLINE = "1"
$env:API_HOST = "127.0.0.1"
$env:API_PORT = "8000"

function Test-ExactVersionOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Output,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )

    $Lines = @(
        $Output -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -ne "" }
    )
    return $Lines.Count -eq 1 -and $Lines[0] -eq $Expected
}

function Test-BackendHealthPayload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    try {
        $Payload = $Content | ConvertFrom-Json
        $Properties = @($Payload.PSObject.Properties)
        return (
            $Properties.Count -eq 2 -and
            $Payload.status -eq "ok" -and
            $Payload.service -eq "intelligent-travel-assistant-api"
        )
    }
    catch {
        return $false
    }
}

function Test-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $Listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    return -not ($Listeners | Where-Object { $_.Port -eq $Port })
}

function Stop-OwnedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    $Stopped = $false
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
            $Stopped = $Process.WaitForExit(5000)
            if (-not $Stopped) {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                $Stopped = $Process.WaitForExit(5000)
            }
        }
        else {
            $Stopped = $true
        }
    }
    catch {
        try {
            $Process.Refresh()
            $Stopped = $Process.HasExited
        }
        catch {
            $Stopped = $true
        }
    }
    finally {
        $Process.Dispose()
    }
    return $Stopped
}

function Invoke-LoopbackRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    $Parsed = [System.Uri]$Uri
    if ($Parsed.Scheme -ne "http" -or $Parsed.Host -ne "127.0.0.1") {
        throw "Runner health checks are restricted to loopback HTTP."
    }

    $Request = [System.Net.HttpWebRequest]::Create($Parsed)
    $Request.Proxy = $null
    $Request.AllowAutoRedirect = $false
    $Request.Timeout = 1000
    $Request.ReadWriteTimeout = 1000
    $Request.Accept = "application/json,text/html"
    $Response = $null
    try {
        $Response = [System.Net.HttpWebResponse]$Request.GetResponse()
        $Reader = New-Object System.IO.StreamReader($Response.GetResponseStream())
        try {
            return [PSCustomObject]@{
                StatusCode = [int]$Response.StatusCode
                Content = $Reader.ReadToEnd()
            }
        }
        finally {
            $Reader.Dispose()
        }
    }
    finally {
        if ($null -ne $Response) {
            $Response.Dispose()
        }
    }
}

function Test-ProcessExited {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    $Process.Refresh()
    return $Process.HasExited
}

function Wait-LoopbackEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [Parameter(Mandatory = $true)]
        [ValidateSet("backend", "frontend")]
        [string]$Kind
    )

    $Deadline = [System.DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    while ([System.DateTime]::UtcNow -lt $Deadline) {
        if (Test-ProcessExited $Process) {
            return "process_exited"
        }
        try {
            $Response = Invoke-LoopbackRequest $Uri
            if (
                $Response.StatusCode -eq 200 -and
                ($Kind -eq "frontend" -or (Test-BackendHealthPayload $Response.Content))
            ) {
                return "ready"
            }
        }
        catch {
            # A bounded loopback connection failure is expected while the child starts.
        }
        Start-Sleep -Milliseconds 250
    }
    return "timeout"
}

function Assert-RepositoryVersionDeclarations {
    $PythonDeclaration = (Get-Content -Raw (Join-Path $ProjectRoot ".python-version")).Trim()
    $NodeDeclaration = (Get-Content -Raw (Join-Path $ProjectRoot ".node-version")).Trim()
    $Package = Get-Content -Raw (Join-Path $ProjectRoot "package.json") | ConvertFrom-Json
    if (
        $PythonDeclaration -ne $ExpectedPython -or
        $NodeDeclaration -ne $ExpectedNode -or
        $Package.packageManager -ne "pnpm@$ExpectedPnpm"
    ) {
        throw "Repository runtime declarations do not match the approved local runner versions."
    }
}

function Assert-ActualVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )

    $Output = (& $Executable @Arguments 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not (Test-ExactVersionOutput $Output $Expected)) {
        throw "$Name runtime version does not match the approved local version $Expected."
    }
}

function Get-SafeFailureMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $ApprovedMessages = @(
        "Repository runtime declarations do not match the approved local runner versions.",
        "Offline backend runtime is unavailable. Run the separately approved install gate first.",
        "Offline frontend runtime is unavailable. Run the separately approved install gate first.",
        "Python runtime version does not match the approved local version Python $ExpectedPython.",
        "Node.js runtime version does not match the approved local version v$ExpectedNode.",
        "pnpm runtime version does not match the approved local version $ExpectedPnpm.",
        "Backend or SQLite local storage could not start. Check the configured database path and permissions.",
        "Backend health did not become ready within 30 seconds.",
        "Frontend could not start on the approved loopback port.",
        "Frontend health did not become ready within 30 seconds.",
        "Backend stopped unexpectedly; the local session is closing.",
        "Frontend stopped unexpectedly; the local session is closing.",
        "Local application child process cleanup did not complete."
    )
    if ($ApprovedMessages -contains $Message) {
        return $Message
    }
    if ($Message -match "^Local port (8000|5173) is already in use; no existing process was stopped\.$") {
        return $Message
    }
    return "Local application could not start safely. Check installed runtimes, fixed ports, and local storage permissions."
}

function Invoke-ContractSelfTest {
    if (-not (Test-ExactVersionOutput "Python 3.13.3" "Python 3.13.3")) {
        throw "Version parser rejected the approved version."
    }
    if (Test-ExactVersionOutput "v22.16.0`nv22.16.0" "v22.16.0") {
        throw "Version parser accepted duplicate output."
    }
    if (Test-ExactVersionOutput "Python 3.13.2" "Python 3.13.3") {
        throw "Version parser accepted a mismatched runtime."
    }
    if (-not (Test-BackendHealthPayload '{"status":"ok","service":"intelligent-travel-assistant-api"}')) {
        throw "Health parser rejected the exact backend contract."
    }
    if (Test-BackendHealthPayload '{"status":"ok","service":"intelligent-travel-assistant-api","extra":true}') {
        throw "Health parser accepted an extra field."
    }

    $FixedListeners = @()
    try {
        foreach ($Port in @($BackendPort, $FrontendPort)) {
            $WasAvailable = Test-PortAvailable $Port
            $Listener = $null
            if ($WasAvailable) {
                $Listener = [System.Net.Sockets.TcpListener]::new(
                    [System.Net.IPAddress]::Loopback,
                    $Port
                )
                $Listener.Start()
            }
            $FixedListeners += [PSCustomObject]@{
                Port = $Port
                Listener = $Listener
                WasAvailable = $WasAvailable
            }
            if (Test-PortAvailable $Port) {
                throw "Port probe missed a fixed-port conflict."
            }
        }
    }
    finally {
        foreach ($Probe in $FixedListeners) {
            if ($null -ne $Probe.Listener) {
                $Probe.Listener.Stop()
            }
        }
    }
    foreach ($Probe in $FixedListeners) {
        if ($Probe.WasAvailable -and -not (Test-PortAvailable $Probe.Port)) {
            throw "Port probe reported a stopped fixed listener."
        }
        if (-not $Probe.WasAvailable -and (Test-PortAvailable $Probe.Port)) {
            throw "Port probe disturbed an existing fixed listener."
        }
    }

    $PowerShell = (Get-Command "powershell.exe" -ErrorAction Stop).Source
    foreach ($Kind in @("backend", "frontend")) {
        $Exited = Start-Process -FilePath $PowerShell -ArgumentList @(
            "-NoProfile",
            "-Command",
            "exit 17"
        ) -PassThru -WindowStyle Hidden
        try {
            if ((Wait-LoopbackEndpoint $Exited "http://127.0.0.1:1/" $Kind) -ne "process_exited") {
                throw "$Kind early exit was not detected."
            }
        }
        finally {
            $null = Stop-OwnedProcess $Exited
        }
    }

    $TimeoutChild = Start-Process -FilePath $PowerShell -ArgumentList @(
        "-NoProfile",
        "-Command",
        "Start-Sleep -Seconds 30"
    ) -PassThru -WindowStyle Hidden
    $OriginalStartupTimeoutSeconds = $StartupTimeoutSeconds
    try {
        $script:StartupTimeoutSeconds = 0
        if ((Wait-LoopbackEndpoint $TimeoutChild "http://127.0.0.1:1/" "backend") -ne "timeout") {
            throw "Backend health timeout was not detected."
        }
        if ((Wait-LoopbackEndpoint $TimeoutChild "http://127.0.0.1:1/" "frontend") -ne "timeout") {
            throw "Frontend health timeout was not detected."
        }
    }
    finally {
        $script:StartupTimeoutSeconds = $OriginalStartupTimeoutSeconds
        $null = Stop-OwnedProcess $TimeoutChild
    }

    $SQLiteFailure = "Backend or SQLite local storage could not start. Check the configured database path and permissions."
    if ((Get-SafeFailureMessage $SQLiteFailure) -ne $SQLiteFailure) {
        throw "SQLite startup failure did not retain its approved safe diagnostic."
    }
    if ((Get-SafeFailureMessage "synthetic-secret-sentinel") -match "sentinel") {
        throw "Unknown runner failure leaked an unapproved diagnostic."
    }

    $Owned = Start-Process -FilePath $PowerShell -ArgumentList @(
        "-NoProfile",
        "-Command",
        "Start-Sleep -Seconds 30"
    ) -PassThru -WindowStyle Hidden
    $Peer = Start-Process -FilePath $PowerShell -ArgumentList @(
        "-NoProfile",
        "-Command",
        "Start-Sleep -Seconds 30"
    ) -PassThru -WindowStyle Hidden
    try {
        if (-not (Stop-OwnedProcess $Owned)) {
            throw "Owned process cleanup did not terminate its exact child."
        }
        $Peer.Refresh()
        if ($Peer.HasExited) {
            throw "Owned process cleanup terminated an unrelated peer."
        }
    }
    finally {
        try {
            $Owned.Dispose()
        }
        catch {
            # Stop-OwnedProcess already disposes the exact owned child.
        }
        $null = Stop-OwnedProcess $Peer
    }

    Write-Output "Local runner contract self-test passed."
}

if ($ContractSelfTest) {
    Invoke-ContractSelfTest
    exit 0
}

$BackendProcess = $null
$FrontendProcess = $null
$ExitCode = 0

Push-Location $ProjectRoot
try {
    Assert-RepositoryVersionDeclarations

    $PythonExecutable = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
    $ViteEntry = Join-Path $ProjectRoot "frontend\node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw "Offline backend runtime is unavailable. Run the separately approved install gate first."
    }
    if (-not (Test-Path -LiteralPath $ViteEntry -PathType Leaf)) {
        throw "Offline frontend runtime is unavailable. Run the separately approved install gate first."
    }

    $NodeExecutable = (Get-Command "node.exe" -ErrorAction Stop).Source
    $CorepackExecutable = (Get-Command "corepack.cmd" -ErrorAction Stop).Source
    Assert-ActualVersion "Python" $PythonExecutable @("--version") "Python $ExpectedPython"
    Assert-ActualVersion "Node.js" $NodeExecutable @("--version") "v$ExpectedNode"
    Assert-ActualVersion "pnpm" $CorepackExecutable @("pnpm", "--version") $ExpectedPnpm

    foreach ($Port in @($BackendPort, $FrontendPort)) {
        if (-not (Test-PortAvailable $Port)) {
            throw "Local port $Port is already in use; no existing process was stopped."
        }
    }

    if ($PreflightOnly) {
        Write-Output "Local runner preflight passed."
        exit 0
    }

    $BackendProcess = Start-Process -FilePath $PythonExecutable -ArgumentList @(
        "-m",
        "intelligent_travel_assistant.main"
    ) -WorkingDirectory (Join-Path $ProjectRoot "backend") -PassThru -WindowStyle Hidden
    $BackendStatus = Wait-LoopbackEndpoint $BackendProcess $BackendHealthUri "backend"
    if ($BackendStatus -eq "process_exited") {
        throw "Backend or SQLite local storage could not start. Check the configured database path and permissions."
    }
    if ($BackendStatus -ne "ready") {
        throw "Backend health did not become ready within 30 seconds."
    }

    $FrontendProcess = Start-Process -FilePath $NodeExecutable -ArgumentList @(
        $ViteEntry,
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
        "--strictPort"
    ) -WorkingDirectory (Join-Path $ProjectRoot "frontend") -PassThru -WindowStyle Hidden
    $FrontendStatus = Wait-LoopbackEndpoint $FrontendProcess $FrontendUri "frontend"
    if ($FrontendStatus -eq "process_exited") {
        throw "Frontend could not start on the approved loopback port."
    }
    if ($FrontendStatus -ne "ready") {
        throw "Frontend health did not become ready within 30 seconds."
    }

    Write-Output $FrontendUri
    while ($true) {
        if (Test-ProcessExited $BackendProcess) {
            throw "Backend stopped unexpectedly; the local session is closing."
        }
        if (Test-ProcessExited $FrontendProcess) {
            throw "Frontend stopped unexpectedly; the local session is closing."
        }
        Start-Sleep -Milliseconds 500
    }
}
catch {
    $ExitCode = 1
    [Console]::Error.WriteLine((Get-SafeFailureMessage $_.Exception.Message))
}
finally {
    $CleanupFailed = $false
    if ($null -ne $FrontendProcess) {
        if (-not (Stop-OwnedProcess $FrontendProcess)) {
            $CleanupFailed = $true
        }
    }
    if ($null -ne $BackendProcess) {
        if (-not (Stop-OwnedProcess $BackendProcess)) {
            $CleanupFailed = $true
        }
    }
    if ($CleanupFailed) {
        $ExitCode = 1
        [Console]::Error.WriteLine(
            (Get-SafeFailureMessage "Local application child process cleanup did not complete.")
        )
    }
    Pop-Location
}

exit $ExitCode
