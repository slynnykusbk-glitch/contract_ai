param(
  [string]$Repo = (Resolve-Path "$PSScriptRoot\.." ).Path
)
$ws = New-Object -ComObject WScript.Shell
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "ContractAI-Start.lnk"
$sc  = $ws.CreateShortcut($lnk)
$sc.TargetPath       = Join-Path $Repo "ContractAI-Start.bat"
$sc.WorkingDirectory = $Repo
$sc.IconLocation     = "shell32.dll,167"
$sc.Save()
Write-Host "Shortcut created:" $lnk

