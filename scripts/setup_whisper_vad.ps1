param(
    [switch]$Force,
    [string]$SourcePath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ModelDir = Join-Path $ProjectRoot ".runtime\voice\whisper_cpp\models"
$ModelName = "ggml-silero-v6.2.0.bin"
$ModelPath = Join-Path $ModelDir $ModelName
$PartialPath = $ModelPath + ".partial"
$ModelUrl = "https://huggingface.co/ggml-org/whisper-vad/resolve/9ffd54a1e1ee413ddf265af9913beaf518d1639b/ggml-silero-v6.2.0.bin"
$ModelPage = "https://huggingface.co/ggml-org/whisper-vad/blob/main/ggml-silero-v6.2.0.bin"
$ExpectedSha256 = "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"
$ExpectedBytes = 885098

New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

function Test-VadModel([string]$Path) {
    if (-not (Test-Path $Path)) { return $false }
    $File = Get-Item $Path
    if ($File.Length -ne $ExpectedBytes) { return $false }
    $Hash = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $Hash -eq $ExpectedSha256
}

function Install-VerifiedLocalModel([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "Local Silero VAD model was not found: $Path"
    }
    if (-not (Test-VadModel $Path)) {
        $Size = (Get-Item $Path).Length
        $Hash = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        throw "Local Silero VAD model verification failed. Expected $ExpectedBytes bytes / SHA256 $ExpectedSha256; got $Size bytes / $Hash."
    }

    Copy-Item $Path $ModelPath -Force
    if (-not (Test-VadModel $ModelPath)) {
        throw "Silero VAD model failed verification after local install."
    }

    Write-Host "Silero VAD model installed from local file and SHA256 verified."
    Write-Host "Model: $ModelPath"
    exit 0
}

function Reset-Partial {
    Remove-Item $PartialPath -Force -ErrorAction SilentlyContinue
}

function Try-CurlDownload {
    $Curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
    if (-not $Curl) { return $false }

    Reset-Partial
    Write-Host "Attempt 1/3: curl.exe (HTTP/1.1, resumable)..."
    & $Curl.Source `
        --fail `
        --location `
        --http1.1 `
        --ssl-revoke-best-effort `
        --connect-timeout 30 `
        --retry 3 `
        --retry-delay 2 `
        --retry-all-errors `
        --continue-at - `
        --output $PartialPath `
        $ModelUrl

    if ($LASTEXITCODE -eq 0 -and (Test-VadModel $PartialPath)) {
        return $true
    }

    Reset-Partial
    return $false
}

function Try-InvokeWebRequestDownload {
    Reset-Partial
    Write-Host "Attempt 2/3: PowerShell Invoke-WebRequest..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest `
            -Uri $ModelUrl `
            -OutFile $PartialPath `
            -UseBasicParsing `
            -MaximumRedirection 10

        if (Test-VadModel $PartialPath) {
            return $true
        }
    }
    catch {
        Write-Warning ("Invoke-WebRequest failed: " + $_.Exception.Message)
    }

    Reset-Partial
    return $false
}

function Try-BitsDownload {
    Reset-Partial
    $Bits = Get-Command "Start-BitsTransfer" -ErrorAction SilentlyContinue
    if (-not $Bits) { return $false }

    Write-Host "Attempt 3/3: Windows BITS..."
    try {
        Start-BitsTransfer -Source $ModelUrl -Destination $PartialPath -ErrorAction Stop
        if (Test-VadModel $PartialPath) {
            return $true
        }
    }
    catch {
        Write-Warning ("BITS download failed: " + $_.Exception.Message)
    }

    Reset-Partial
    return $false
}

if ($Force) {
    Remove-Item $ModelPath, $PartialPath -Force -ErrorAction SilentlyContinue
}

if (Test-VadModel $ModelPath) {
    Write-Host "Silero VAD model already present and checksum verified."
    Write-Host "Model: $ModelPath"
    exit 0
}

if (Test-Path $ModelPath) {
    Write-Warning "Existing Silero VAD model is invalid; removing it."
    Remove-Item $ModelPath -Force
}
Reset-Partial

# First-class offline/manual path for networks that reset Hugging Face's Xet/CDN.
if ($SourcePath) {
    $Resolved = (Resolve-Path $SourcePath).Path
    Install-VerifiedLocalModel $Resolved
}

# Also accept a manually downloaded file dropped into the project root.
$ProjectDrop = Join-Path $ProjectRoot $ModelName
if (Test-Path $ProjectDrop) {
    Write-Host "Found $ModelName in project root; verifying..."
    Install-VerifiedLocalModel $ProjectDrop
}

Write-Host "Downloading Silero VAD v6.2.0 (~865 KiB)..."

$Downloaded = $false
if (Try-CurlDownload) {
    $Downloaded = $true
}
elseif (Try-InvokeWebRequestDownload) {
    $Downloaded = $true
}
elseif (Try-BitsDownload) {
    $Downloaded = $true
}

if (-not $Downloaded) {
    Reset-Partial
    Write-Host ""
    Write-Host "Automatic download failed through curl, Invoke-WebRequest, and BITS." -ForegroundColor Yellow
    Write-Host "The network appears to be resetting the Hugging Face Xet/CDN transfer."
    Write-Host ""
    Write-Host "Manual fallback:"
    Write-Host "  1. Open this official model page in your browser:"
    Write-Host "     $ModelPage"
    Write-Host "  2. Click Download."
    Write-Host "  3. Then run:"
    Write-Host "     powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_vad.ps1 -SourcePath `"$env:USERPROFILE\Downloads\$ModelName`""
    Write-Host ""
    Write-Host "The file is still rejected unless it matches the pinned size and SHA256."
    throw "Silero VAD model download failed through all automatic clients."
}

Move-Item $PartialPath $ModelPath -Force
if (-not (Test-VadModel $ModelPath)) {
    throw "Silero VAD model verification failed after download."
}

Write-Host "Silero VAD model installed and SHA256 verified."
Write-Host "Model: $ModelPath"
