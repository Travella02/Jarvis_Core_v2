param(
    [ValidateSet("modern-cuda", "official", "cpu")]
    [string]$Profile = "modern-cuda",
    [switch]$Force,
    [switch]$ForceModelDownload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot ".runtime\voice\chatterbox"
$Venv = Join-Path $RuntimeRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$MainPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ModelDir = Join-Path $RuntimeRoot "models\chatterbox-turbo"
$ModelRevision = "1e4698ca7cbb41ff030c4185f0927a3b42d76924"
$ModelBaseUrl = "https://huggingface.co/ResembleAI/chatterbox-turbo/resolve/$ModelRevision"
$ModernTorchVersion = "2.7.1"
$ModernTorchIndex = "https://download.pytorch.org/whl/cu128"

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function Test-DownloadedFile {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [string]$ExpectedSha256 = ""
    )
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    if ((Get-Item $Path).Length -le 0) { return $false }
    if ($ExpectedSha256) {
        return (Get-Sha256Hex -Path $Path) -eq $ExpectedSha256.ToLowerInvariant()
    }
    return $true
}

function Invoke-CurlDownload {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$PartialPath,
        [switch]$Resume
    )
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return $false }
    $args = @(
        "--location",
        "--fail",
        "--show-error",
        "--retry", "8",
        "--retry-delay", "2",
        "--retry-all-errors",
        "--connect-timeout", "30",
        "--speed-time", "45",
        "--speed-limit", "1024"
    )
    if ($Resume -and (Test-Path $PartialPath)) {
        $args += @("--continue-at", "-")
    }
    $args += @("--output", $PartialPath, $Uri)
    & $curl.Source @args
    return $LASTEXITCODE -eq 0
}

function Invoke-BitsFallback {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    $bits = Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue
    if (-not $bits) { return $false }
    try {
        if (Test-Path $Destination) { Remove-Item $Destination -Force }
        Start-BitsTransfer -Source $Uri -Destination $Destination -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "BITS fallback failed: $($_.Exception.Message)"
        return $false
    }
}

function Install-ModelAsset {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [string]$ExpectedSha256 = ""
    )
    $destination = Join-Path $ModelDir $Name
    $partial = "$destination.partial"
    $escapedName = [System.Uri]::EscapeDataString($Name)
    $uri = ("{0}/{1}" -f $ModelBaseUrl.TrimEnd("/"), $escapedName)

    if ($ForceModelDownload) {
        Remove-Item $destination -Force -ErrorAction SilentlyContinue
        Remove-Item $partial -Force -ErrorAction SilentlyContinue
    }

    if (Test-DownloadedFile -Path $destination -ExpectedSha256 $ExpectedSha256) {
        Write-Host "Model asset already verified: $Name"
        return
    }
    if (Test-Path $destination) {
        Write-Warning "Existing model asset failed validation and will be replaced: $Name"
        Remove-Item $destination -Force
    }

    Write-Host "Downloading Chatterbox model asset: $Name"
    $resume = Test-Path $partial
    $ok = Invoke-CurlDownload -Uri $uri -PartialPath $partial -Resume:$resume
    if (-not $ok -and $resume) {
        Write-Warning "Resume failed for $Name; retrying once from byte 0."
        Remove-Item $partial -Force -ErrorAction SilentlyContinue
        $ok = Invoke-CurlDownload -Uri $uri -PartialPath $partial
    }
    if (-not $ok) {
        Write-Warning "curl.exe could not finish $Name; trying Windows BITS from byte 0."
        $ok = Invoke-BitsFallback -Uri $uri -Destination $partial
    }
    if (-not $ok) {
        throw "Unable to download Chatterbox model asset '$Name' after curl retry/resume and BITS fallback."
    }
    if (-not (Test-DownloadedFile -Path $partial -ExpectedSha256 $ExpectedSha256)) {
        Remove-Item $partial -Force -ErrorAction SilentlyContinue
        if ($ExpectedSha256) {
            throw "Checksum verification failed for Chatterbox model asset '$Name'."
        }
        throw "Downloaded Chatterbox model asset '$Name' is empty or invalid."
    }
    Move-Item -Path $partial -Destination $destination -Force
    Write-Host "Installed model asset: $Name"
}

if (-not (Test-Path $MainPython)) {
    throw "Jarvis project .venv was not found at $MainPython"
}
if ($Force -and (Test-Path $Venv)) {
    Remove-Item $Venv -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
if (-not (Test-Path $Python)) {
    & $MainPython -m venv $Venv
}
& $Python -m pip install --upgrade pip setuptools wheel

if ($Profile -eq "official") {
    Write-Host "Installing upstream Chatterbox dependency pins (Torch 2.6)."
    & $Python -m pip install "chatterbox-tts==0.1.7"
} else {
    if ($Profile -eq "modern-cuda") {
        Write-Host "Installing Blackwell-compatible PyTorch $ModernTorchVersion + CUDA 12.8 runtime."
        Write-Host "This intentionally overrides Chatterbox 0.1.7's older Torch 2.6 metadata pin inside the isolated TTS runtime."
        & $Python -m pip install --upgrade --force-reinstall "torch==$ModernTorchVersion" "torchaudio==$ModernTorchVersion" --index-url $ModernTorchIndex
    } else {
        & $Python -m pip install --upgrade --force-reinstall "torch==$ModernTorchVersion" "torchaudio==$ModernTorchVersion" --index-url https://download.pytorch.org/whl/cpu
    }
    if ($LASTEXITCODE -ne 0) { throw "PyTorch installation failed." }

    & $Python -m pip install --upgrade --force-reinstall "chatterbox-tts==0.1.7" --no-deps
    & $Python -m pip install --upgrade `
        "numpy>=1.24.0,<2.0.0" `
        "librosa==0.11.0" `
        "s3tokenizer" `
        "transformers==5.2.0" `
        "diffusers==0.29.0" `
        "resemble-perth @ git+https://github.com/resemble-ai/Perth.git@master" `
        "conformer==0.3.2" `
        "safetensors==0.5.3" `
        "spacy-pkuseg" `
        "pykakasi==2.3.0" `
        "gradio==6.8.0" `
        "pyloudnorm" `
        "omegaconf"
}
if ($LASTEXITCODE -ne 0) { throw "Chatterbox dependency installation failed." }

& $Python -c "import torch; from chatterbox.tts_turbo import ChatterboxTurboTTS; print('torch=' + torch.__version__); print('cuda=' + str(torch.cuda.is_available())); print('device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')); print('chatterbox import=ok'); print('cuda-smoke=' + str(float(torch.ones(1, device='cuda').sum().item())) if torch.cuda.is_available() else 'cuda-smoke=skipped')"
if ($LASTEXITCODE -ne 0) { throw "Chatterbox runtime validation failed." }

Write-Host "Preparing pinned local Chatterbox Turbo model assets (~3 GiB required for the Jarvis Turbo path)."
$ModelFiles = @(
    @{ Name = "t3_turbo_v1.safetensors"; Sha256 = "fcf1f8c1d651bb7e3acd69ee5be269b4ac10c02980b7708213d598bc9f7cdf87" },
    @{ Name = "s3gen_meanflow.safetensors"; Sha256 = "d65cb687a2ed581ee6cc297e919ffefa63386944f42364ae13b78a594945514f" },
    @{ Name = "ve.safetensors"; Sha256 = "f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c" },
    @{ Name = "conds.pt"; Sha256 = "b1852099306fd6a7814eb9d0bd10186caba7249596cc23868f78a0eefbfa5033" },
    @{ Name = "tokenizer_config.json"; Sha256 = "" },
    @{ Name = "vocab.json"; Sha256 = "" },
    @{ Name = "merges.txt"; Sha256 = "" },
    @{ Name = "special_tokens_map.json"; Sha256 = "" },
    @{ Name = "added_tokens.json"; Sha256 = "" }
)
foreach ($entry in $ModelFiles) {
    Install-ModelAsset -Name $entry.Name -ExpectedSha256 $entry.Sha256
}

& $Python -c "from pathlib import Path; from transformers import AutoTokenizer; p=Path(r'$ModelDir'); t=AutoTokenizer.from_pretrained(p); assert len(t)==50276, len(t); print('chatterbox-model-assets=ready'); print('tokenizer-size=' + str(len(t)))"
if ($LASTEXITCODE -ne 0) { throw "Chatterbox local model asset validation failed." }

Write-Host "Chatterbox isolated runtime ready: $Python"
Write-Host "Runtime profile: $Profile"
if ($Profile -eq "modern-cuda") {
    Write-Host "Pinned compatibility runtime: torch/torchaudio $ModernTorchVersion + cu128"
}
Write-Host "Local model directory: $ModelDir"
Write-Host "Chatterbox startup is now offline/local after these assets are installed; provider-health no longer downloads model weights."
Write-Host "If startup fails, Jarvis preserves the sidecar traceback under .runtime\voice\chatterbox\logs\sidecar-stderr.log."
