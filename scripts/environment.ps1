$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($ProjectRoot -ne 'D:\projefikri\kas_animasyon') {
    throw 'Bu çalışma yalnızca D:\projefikri\kas_animasyon içinde çalıştırılır.'
}
$RuntimeRoot = Join-Path $ProjectRoot '.runtime'
foreach ($Folder in @('temp', 'cache', 'home', 'appdata', 'localappdata', 'python', 'tools', 'config')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot $Folder) | Out-Null
}
$env:TEMP = Join-Path $RuntimeRoot 'temp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:XDG_CACHE_HOME = Join-Path $RuntimeRoot 'cache'
$env:XDG_CONFIG_HOME = Join-Path $RuntimeRoot 'config'
$env:APPDATA = Join-Path $RuntimeRoot 'appdata'
$env:LOCALAPPDATA = Join-Path $RuntimeRoot 'localappdata'
$env:UV_CACHE_DIR = Join-Path $RuntimeRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $RuntimeRoot 'python'
$env:UV_PYTHON_BIN_DIR = Join-Path $RuntimeRoot 'tools\bin'
$env:UV_TOOL_BIN_DIR = Join-Path $RuntimeRoot 'tools\bin'
$env:UV_TOOL_DIR = Join-Path $RuntimeRoot 'tools'
$env:UV_NO_PROGRESS = '1'
$env:PIP_CACHE_DIR = Join-Path $RuntimeRoot 'cache\pip'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:MPLCONFIGDIR = Join-Path $RuntimeRoot 'cache\matplotlib'
$env:TORCH_HOME = Join-Path $RuntimeRoot 'cache\torch'
$env:TORCH_EXTENSIONS_DIR = Join-Path $RuntimeRoot 'cache\torch_extensions'
$env:TORCHINDUCTOR_CACHE_DIR = Join-Path $RuntimeRoot 'cache\torchinductor'
$env:PYTORCH_KERNEL_CACHE_PATH = Join-Path $RuntimeRoot 'cache\torch_kernels'
$env:TRITON_CACHE_DIR = Join-Path $RuntimeRoot 'cache\triton'
$env:JOBLIB_TEMP_FOLDER = Join-Path $RuntimeRoot 'temp\joblib'
$env:HF_HOME = Join-Path $RuntimeRoot 'cache\huggingface'
$env:NUMBA_CACHE_DIR = Join-Path $RuntimeRoot 'cache\numba'
$env:CUDA_CACHE_PATH = Join-Path $RuntimeRoot 'cache\cuda'
$env:GIT_CONFIG_GLOBAL = Join-Path $RuntimeRoot 'config\gitconfig'
$env:GIT_CONFIG_NOSYSTEM = '1'
$env:GIT_TERMINAL_PROMPT = '0'
$env:MUJOCO_LOG_PATH = Join-Path $RuntimeRoot 'temp\MUJOCO_LOG.TXT'
Set-Location -LiteralPath $ProjectRoot
