$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeRoot = Join-Path $ProjectRoot ".runtime\voice\qwen3_tts_streaming_candidate"
$SourceRoot = Join-Path $RuntimeRoot "source"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$PythonExe = Join-Path $VenvRoot "Scripts\python.exe"

Write-Host "Repair22 EXPERIMENTAL runtime only. The accepted Repair20 Qwen runtime will not be modified."

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git is required." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python Launcher (py.exe) is required." }
& py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required by the streaming candidate. Install Python 3.12, then rerun." }

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
if (-not (Test-Path $SourceRoot)) {
    git clone https://github.com/dffdeeq/Qwen3-TTS-streaming.git $SourceRoot
} else {
    Write-Host "Candidate source already exists; leaving it pinned to the existing checkout."
}
if (-not (Test-Path $PythonExe)) {
    & py -3.12 -m venv $VenvRoot
}

& $PythonExe -m pip install --upgrade pip setuptools wheel
& $PythonExe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
& $PythonExe -m pip install "https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.12/flash_attn-2.8.3%2Bcu130torch2.10-cp312-cp312-win_amd64.whl"
& $PythonExe -m pip install -U "triton-windows<3.7"
& $PythonExe -m pip install sounddevice soundfile
& $PythonExe -m pip install -e $SourceRoot

& $PythonExe -c "import torch; from qwen_tts import Qwen3TTSModel; print('torch=' + torch.__version__); print('cuda=' + str(torch.cuda.is_available())); print('gpu=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')); assert torch.cuda.is_available(); assert hasattr(Qwen3TTSModel, 'stream_generate_voice_clone'); print('stream_generate_voice_clone=available')"
if ($LASTEXITCODE -ne 0) { throw "Streaming candidate validation failed." }

Write-Host ""
Write-Host "Repair22 streaming candidate runtime is ready."
Write-Host "It reuses the existing Repair20 Qwen model assets and does not replace the accepted provider."
Write-Host "Next: python -m apps.qwen_streaming_candidate --voice-profile tanner-test"
