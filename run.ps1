param([switch]$SkipMySQL)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $bootstrapPython = $pythonCommand.Source
    } else {
        $bootstrapPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    }
    if (-not (Test-Path -LiteralPath $bootstrapPython)) { throw '请安装 Python 3.12，并加入 PATH。' }
    & $bootstrapPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
    & $projectPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络。' }
}
& $projectPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '边界测试失败，已停止运行。' }
if ($SkipMySQL) {
    & $projectPython run_pipeline.py --skip-mysql
} else {
    & $projectPython run_pipeline.py
}
if ($LASTEXITCODE -ne 0) { throw '分析失败，请查看上面的报错和 runtime 日志。' }
Write-Host '分析完成：outputs/analysis_report.html'
