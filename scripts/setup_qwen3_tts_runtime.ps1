param(
    [ValidateSet("modern-cuda", "cpu")]
    [string]$Profile = "modern-cuda"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeRoot = Join-Path $ProjectRoot ".runtime\voice\qwen3_tts"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$PythonExe = Join-Path $VenvRoot "Scripts\python.exe"
$ModelDir = Join-Path $RuntimeRoot "models\Qwen3-TTS-12Hz-0.6B-Base"
$Downloader = Join-Path $ProjectRoot "scripts\download_qwen3_tts_model.py"

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
if (-not (Test-Path $PythonExe)) {
    Write-Host "Creating isolated Qwen3-TTS runtime..."
    python -m venv $VenvRoot
}

& $PythonExe -m pip install --upgrade pip setuptools wheel
& $PythonExe -m pip install "qwen-tts==0.1.1" "huggingface_hub[hf_xet]>=0.34"

if ($Profile -eq "modern-cuda") {
    Write-Host "Pinning Blackwell-compatible PyTorch 2.7.1 + CUDA 12.8..."
    & $PythonExe -m pip install --upgrade --force-reinstall `
        "torch==2.7.1+cu128" "torchaudio==2.7.1+cu128" `
        --index-url https://download.pytorch.org/whl/cu128
} else {
    & $PythonExe -m pip install --upgrade "torch==2.7.1" "torchaudio==2.7.1"
}

& $PythonExe -c @"
import torch
from qwen_tts import Qwen3TTSModel
print(f'torch={torch.__version__}')
print(f'cuda={torch.cuda.is_available()}')
print(f'device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}')
print('qwen_tts import=ok')
if '$Profile' == 'modern-cuda':
    assert torch.cuda.is_available(), 'CUDA is not available in the Qwen runtime'
    print(f'cuda-smoke={float((torch.ones(1, device="cuda") + 1).item())}')
"@

Write-Host "Downloading/resuming official Qwen3-TTS 0.6B Base model (~2.5 GB full snapshot)..."
& $PythonExe $Downloader --repo "Qwen/Qwen3-TTS-12Hz-0.6B-Base" --local-dir $ModelDir

Write-Host "Qwen3-TTS isolated runtime ready: $PythonExe"
Write-Host "Runtime profile: $Profile"
Write-Host "Local model directory: $ModelDir"
Write-Host "FlashAttention is intentionally not required for the first A/B test; Jarvis uses SDPA initially."
