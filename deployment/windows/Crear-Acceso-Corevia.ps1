param(
    [Parameter(Mandatory=$true)][uri]$Url,
    [string]$Icon = (Join-Path $PSScriptRoot '..\..\static\brand\corevia.ico')
)
$ErrorActionPreference = 'Stop'
if ($Url.Scheme -ne 'https' -or $Url.UserInfo -or $Url.Query -or $Url.Fragment) {
    throw 'Usá la dirección HTTPS interna de Corevia, sin credenciales ni parámetros.'
}
if (-not (Test-Path -LiteralPath $Icon)) { throw 'No se encontró el ícono Corevia.' }
$folder = Join-Path $env:LOCALAPPDATA 'Corevia'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$localIcon = Join-Path $folder 'corevia.ico'
Copy-Item -LiteralPath $Icon -Destination $localIcon -Force
$desktop = [Environment]::GetFolderPath('Desktop')
$content = "[InternetShortcut]`r`nURL=$($Url.AbsoluteUri)`r`nIconFile=$localIcon`r`nIconIndex=0`r`n"
[IO.File]::WriteAllText((Join-Path $desktop 'Corevia.url'), $content, [Text.UTF8Encoding]::new($false))
Write-Output 'Acceso Corevia creado para el usuario actual. No se instaló un servidor en esta computadora.'
