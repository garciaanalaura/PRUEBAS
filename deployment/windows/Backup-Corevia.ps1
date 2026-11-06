param(
    [string]$Python = 'C:\Corevia\venv\Scripts\python.exe',
    [string]$Project = 'C:\Corevia\current',
    [string]$Config = 'C:\ProgramData\Corevia\config\corevia.toml'
)
$ErrorActionPreference = 'Stop'
$env:COREVIA_CONFIG = $Config
& $Python (Join-Path $Project 'manage.py') backup
exit $LASTEXITCODE
