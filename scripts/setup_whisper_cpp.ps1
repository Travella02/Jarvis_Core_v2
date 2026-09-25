param(
    [ValidateSet("cuda", "cpu")]
    [string]$Backend = "cuda",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot ".runtime\voice\whisper_cpp"
$SourceDir = Join-Path $RuntimeRoot "src"
# Backend-specific build trees prevent a failed CUDA/VS configure from poisoning
# later CPU/GPU setup attempts through CMake's persistent generator cache.
$BuildDir = Join-Path $RuntimeRoot ("build-" + $Backend)
$BinDir = Join-Path $RuntimeRoot "bin"
$ModelDir = Join-Path $RuntimeRoot "models"
$ModelPath = Join-Path $ModelDir "ggml-large-v3-turbo-q5_0.bin"
$ModelUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
$ExpectedSha1 = "e050f7970618a659205450ad97eb95a18d69c9ee"
$WhisperTag = "v1.9.4"

function Require-Command([string]$Name, [string]$Help) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required. $Help"
    }
}

function Get-CudaVersion {
    $nvccOutput = (& nvcc --version 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "nvcc is installed but 'nvcc --version' failed. Reopen PowerShell after installing the CUDA Toolkit."
    }
    if ($nvccOutput -notmatch 'release\s+(\d+)\.(\d+)') {
        throw "Unable to determine the CUDA Toolkit version from nvcc --version."
    }
    return [version]("{0}.{1}" -f $Matches[1], $Matches[2])
}

function Test-VisualStudioCppTools([string]$InstallPath) {
    if (-not $InstallPath -or -not (Test-Path $InstallPath)) {
        return $false
    }
    $MsvcRoot = Join-Path $InstallPath "VC\Tools\MSVC"
    if (-not (Test-Path $MsvcRoot)) {
        return $false
    }
    $Compiler = Get-ChildItem $MsvcRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "bin\Hostx64\x64\cl.exe" } |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1
    return [bool]$Compiler
}

function Find-VisualStudio2022 {
    $ProgramFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $VsWhere = Join-Path $ProgramFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $VsWhere) {
        $Found = (& $VsWhere -latest -products * -version "[17.0,18.0)" -requires "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" -property installationPath 2>$null | Select-Object -First 1)
        if ($Found) {
            $Found = $Found.Trim()
            if (Test-VisualStudioCppTools $Found) {
                return $Found
            }
        }
    }

    $Base = Join-Path $ProgramFilesX86 "Microsoft Visual Studio\2022"
    foreach ($Edition in @("BuildTools", "Community", "Professional", "Enterprise")) {
        $Candidate = Join-Path $Base $Edition
        if (Test-VisualStudioCppTools $Candidate) {
            return $Candidate
        }
    }
    return $null
}

function Get-CudaBuildToolchain {
    $CudaVersion = Get-CudaVersion

    # 0.0.4 intentionally pins CUDA builds to the VS 2022/v143 toolchain. CUDA
    # 12.8 officially supports VS 2022 (MSVC 193x), while the VS 2026/v145
    # toolchain that CMake may auto-select is not supported by CUDA 12.8.
    $Vs2022 = Find-VisualStudio2022
    if (-not $Vs2022) {
        $InstallHint = 'winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"'
        throw "CUDA $CudaVersion is installed, but a compatible Visual Studio 2022 C++ toolchain was not found. Install Visual Studio 2022 Build Tools with Desktop development with C++ (v143), reopen PowerShell/VS Code, then retry. Example: $InstallHint"
    }

    $NvccPath = (Get-Command nvcc -ErrorAction Stop).Source
    $CudaRoot = Split-Path -Parent (Split-Path -Parent $NvccPath)
    $IntegrationDir = Join-Path $CudaRoot "extras\visual_studio_integration\MSBuildExtensions"
    $CudaLabel = "{0}.{1}" -f $CudaVersion.Major, $CudaVersion.Minor
    $PropsPath = Join-Path $IntegrationDir ("CUDA " + $CudaLabel + ".props")
    $TargetsPath = Join-Path $IntegrationDir ("CUDA " + $CudaLabel + ".targets")
    if (-not (Test-Path $PropsPath) -or -not (Test-Path $TargetsPath)) {
        throw "CUDA $CudaLabel Visual Studio integration files were not found under $IntegrationDir. Rerun the CUDA $CudaLabel installer and ensure CUDA > Visual Studio Integration is installed, then retry."
    }

    return [PSCustomObject]@{
        CudaVersion = $CudaVersion
        CudaRoot = $CudaRoot
        Generator = "Visual Studio 17 2022"
        Instance = $Vs2022
        Architecture = "x64"
        Toolset = "cuda=$CudaRoot,host=x64"
    }
}

function Normalize-PathText([string]$Value) {
    if (-not $Value) { return "" }
    return (($Value -replace '\\', '/').TrimEnd('/')).ToLowerInvariant()
}

function Reset-IncompatibleCMakeCache([string]$Directory, [string]$ExpectedGenerator, [string]$ExpectedInstance, [string]$ExpectedToolset) {
    $Cache = Join-Path $Directory "CMakeCache.txt"
    if (-not (Test-Path $Cache)) {
        return
    }
    $GeneratorLine = Get-Content $Cache | Where-Object { $_ -like "CMAKE_GENERATOR:INTERNAL=*" } | Select-Object -First 1
    $InstanceLine = Get-Content $Cache | Where-Object { $_ -like "CMAKE_GENERATOR_INSTANCE:INTERNAL=*" } | Select-Object -First 1
    $ToolsetLine = Get-Content $Cache | Where-Object { $_ -like "CMAKE_GENERATOR_TOOLSET:INTERNAL=*" } | Select-Object -First 1
    $CurrentGenerator = if ($GeneratorLine) { ($GeneratorLine -split '=', 2)[1] } else { "" }
    $CurrentInstance = if ($InstanceLine) { ($InstanceLine -split '=', 2)[1] } else { "" }
    $CurrentToolset = if ($ToolsetLine) { ($ToolsetLine -split '=', 2)[1] } else { "" }

    $GeneratorMismatch = $CurrentGenerator -ne $ExpectedGenerator
    $InstanceMismatch = (Normalize-PathText $CurrentInstance) -ne (Normalize-PathText $ExpectedInstance)
    $ToolsetMismatch = (Normalize-PathText $CurrentToolset) -ne (Normalize-PathText $ExpectedToolset)
    if ($GeneratorMismatch -or $InstanceMismatch -or $ToolsetMismatch) {
        Write-Host "Removing stale CMake cache configured for an incompatible Visual Studio instance..."
        Remove-Item $Directory -Recurse -Force
    }
}

Require-Command git "Install Git for Windows and reopen PowerShell."
Require-Command cmake "Install CMake and make sure cmake.exe is on PATH."
$CudaToolchain = $null
if ($Backend -eq "cuda") {
    Require-Command nvcc "Install the NVIDIA CUDA Toolkit before building the GPU runtime."
    $CudaToolchain = Get-CudaBuildToolchain
    Write-Host "CUDA toolkit: $($CudaToolchain.CudaVersion)"
    Write-Host "CMake generator: $($CudaToolchain.Generator)"
    Write-Host "Visual Studio instance: $($CudaToolchain.Instance)"
    Write-Host "CUDA toolset root: $($CudaToolchain.CudaRoot)"
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $BinDir, $ModelDir | Out-Null

if ($Force -and (Test-Path $SourceDir)) {
    Remove-Item $SourceDir -Recurse -Force
}
if ($Force -and (Test-Path $BuildDir)) {
    Remove-Item $BuildDir -Recurse -Force
}
if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
    git clone --depth 1 --branch $WhisperTag https://github.com/ggml-org/whisper.cpp.git $SourceDir
    if ($LASTEXITCODE -ne 0) { throw "whisper.cpp clone failed." }
} else {
    git -C $SourceDir fetch --tags --force
    if ($LASTEXITCODE -ne 0) { throw "whisper.cpp tag refresh failed." }
    git -C $SourceDir checkout $WhisperTag
    if ($LASTEXITCODE -ne 0) { throw "whisper.cpp checkout failed." }
}

$CmakeArgs = @("-S", $SourceDir, "-B", $BuildDir, "-DWHISPER_BUILD_TESTS=OFF")
if ($Backend -eq "cuda") {
    Reset-IncompatibleCMakeCache $BuildDir $CudaToolchain.Generator $CudaToolchain.Instance $CudaToolchain.Toolset
    $CmakeArgs += @(
        "-G", $CudaToolchain.Generator,
        "-A", $CudaToolchain.Architecture,
        "-T", $CudaToolchain.Toolset,
        "-DCMAKE_GENERATOR_INSTANCE=$($CudaToolchain.Instance)",
        "-DGGML_CUDA=ON"
    )
} else {
    $CmakeArgs += "-DGGML_CUDA=OFF"
}

& cmake @CmakeArgs
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed." }
& cmake --build $BuildDir --config Release --target whisper-server -j
if ($LASTEXITCODE -ne 0) { throw "whisper-server build failed." }

$Server = Get-ChildItem $BuildDir -Recurse -Filter "whisper-server.exe" | Select-Object -First 1
if (-not $Server) { throw "Build completed but whisper-server.exe was not found." }
$BuiltBin = $Server.Directory.FullName
Get-ChildItem $BuiltBin -File | Where-Object { $_.Extension -in ".exe", ".dll" } | Copy-Item -Destination $BinDir -Force

function Get-FileSha1([string]$Path) {
    if (-not (Test-Path $Path)) {
        return $null
    }
    return (Get-FileHash $Path -Algorithm SHA1).Hash.ToLowerInvariant()
}

function Test-ExpectedModelHash([string]$Path, [string]$ExpectedSha1) {
    $Actual = Get-FileSha1 $Path
    return [bool]($Actual -and $Actual -eq $ExpectedSha1)
}

function Invoke-CurlModelDownload([string]$Url, [string]$PartialPath) {
    $Curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
    if (-not $Curl) {
        Write-Warning "curl.exe is unavailable; skipping the resumable curl downloader."
        return $false
    }

    for ($Attempt = 1; $Attempt -le 4; $Attempt++) {
        $CurlArgs = @(
            "--fail",
            "--location",
            "--progress-bar",
            "--connect-timeout", "30",
            "--retry", "3",
            "--retry-delay", "2",
            "--retry-all-errors"
        )
        if ((Test-Path $PartialPath) -and (Get-Item $PartialPath).Length -gt 0) {
            Write-Host "Resuming partial model download (curl attempt $Attempt/4)..."
            $CurlArgs += @("--continue-at", "-")
        } else {
            Write-Host "Starting model download (curl attempt $Attempt/4)..."
        }
        $CurlArgs += @("--output", $PartialPath, $Url)

        & $Curl.Source @CurlArgs
        $ExitCode = $LASTEXITCODE
        if ($ExitCode -eq 0) {
            return $true
        }

        # curl exit code 33 means the server refused the requested byte range.
        # Drop only the resumable temp file and retry cleanly rather than keeping
        # a partial that can never be resumed from this endpoint.
        if ($ExitCode -eq 33 -and (Test-Path $PartialPath)) {
            Write-Warning "The server refused the resume range; restarting the model download from byte 0."
            Remove-Item $PartialPath -Force
        } else {
            Write-Warning "curl model download attempt $Attempt failed with exit code $ExitCode."
        }
        if ($Attempt -lt 4) {
            Start-Sleep -Seconds ([Math]::Min(2 * $Attempt, 8))
        }
    }
    return $false
}

function Invoke-BitsModelDownload([string]$Url, [string]$PartialPath) {
    Import-Module BitsTransfer -ErrorAction SilentlyContinue
    if (-not (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue)) {
        Write-Warning "BITS is unavailable; skipping the Windows BITS fallback downloader."
        return $false
    }

    $BitsPath = $PartialPath + ".bits"
    Remove-Item $BitsPath -Force -ErrorAction SilentlyContinue
    try {
        Write-Host "Trying Windows BITS fallback download..."
        Start-BitsTransfer -Source $Url -Destination $BitsPath -Priority Foreground -ErrorAction Stop
        Move-Item $BitsPath $PartialPath -Force
        return $true
    } catch {
        Write-Warning "BITS model download failed: $($_.Exception.Message)"
        Remove-Item $BitsPath -Force -ErrorAction SilentlyContinue
        return $false
    }
}

function Invoke-ModelDownload([string]$Url, [string]$PartialPath) {
    if (Invoke-CurlModelDownload $Url $PartialPath) {
        return $true
    }
    Write-Warning "Resumable curl download did not complete; falling back to BITS."
    return (Invoke-BitsModelDownload $Url $PartialPath)
}

function Ensure-WhisperModel {
    $PartialPath = $ModelPath + ".partial"
    $BitsPath = $PartialPath + ".bits"

    if ($Force) {
        Remove-Item $ModelPath, $PartialPath, $BitsPath -Force -ErrorAction SilentlyContinue
    }

    if (Test-ExpectedModelHash $ModelPath $ExpectedSha1) {
        Write-Host "Whisper model already present and checksum verified."
        return
    }

    # Older 0.0.4 setup attempts wrote directly to the final model path. Preserve
    # a truncated file as the resumable partial instead of throwing away hundreds
    # of MiB that may already be valid.
    if (Test-Path $ModelPath) {
        Write-Warning "Existing Whisper model is incomplete or has the wrong checksum."
        if (-not (Test-Path $PartialPath)) {
            Move-Item $ModelPath $PartialPath -Force
            Write-Host "Preserved the existing bytes as a resumable partial download."
        } else {
            Remove-Item $ModelPath -Force
        }
    }

    Write-Host "Downloading Whisper large-v3-turbo-q5_0 (~547 MiB) with retry/resume support..."
    $Downloaded = Invoke-ModelDownload $ModelUrl $PartialPath
    if (-not $Downloaded -or -not (Test-Path $PartialPath)) {
        throw "Automatic Whisper model download failed after retry/resume and BITS fallback. You can manually download $ModelUrl to $ModelPath, then rerun this script; the SHA1 will still be verified before Jarvis accepts it."
    }

    $ActualSha1 = Get-FileSha1 $PartialPath
    if ($ActualSha1 -ne $ExpectedSha1) {
        # A resumed file can be invalid if a prior failed downloader wrote a bad
        # prefix. Make exactly one clean full-download attempt before failing.
        Write-Warning "Downloaded model checksum mismatch after resume. Retrying once from byte 0..."
        Remove-Item $PartialPath -Force
        $Downloaded = Invoke-ModelDownload $ModelUrl $PartialPath
        if (-not $Downloaded -or -not (Test-Path $PartialPath)) {
            throw "Fresh Whisper model redownload failed. Expected SHA1 $ExpectedSha1."
        }
        $ActualSha1 = Get-FileSha1 $PartialPath
        if ($ActualSha1 -ne $ExpectedSha1) {
            Remove-Item $PartialPath -Force -ErrorAction SilentlyContinue
            throw "Whisper model SHA1 mismatch after a fresh redownload. Expected $ExpectedSha1 but got $ActualSha1. The invalid partial file was removed."
        }
    }

    Move-Item $PartialPath $ModelPath -Force
    Write-Host "Whisper model checksum verified and installed atomically."
}

Ensure-WhisperModel

Write-Host "Whisper runtime ready."
Write-Host "Backend: $Backend"
Write-Host "Server: $(Join-Path $BinDir 'whisper-server.exe')"
Write-Host "Model:  $ModelPath"
