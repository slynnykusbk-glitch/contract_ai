$repo = Split-Path -Parent $PSScriptRoot
. "$repo/tools/start_oneclick.ps1"

describe "Load-DotEnv" {
  it "loads env without overriding existing" {
    $tmp = New-TemporaryFile
    Set-Content $tmp "EXIST=fromenv`nNEWVAR=fromenv"
    [System.Environment]::SetEnvironmentVariable('EXIST','orig','Process')
    Load-DotEnv $tmp
    [System.Environment]::GetEnvironmentVariable('EXIST','Process') | Should -Be 'orig'
    [System.Environment]::GetEnvironmentVariable('NEWVAR','Process') | Should -Be 'fromenv'
  }
}

describe "Wait-BackendHealth" {
  it "returns false when backend missing" {
    Wait-BackendHealth -Url 'https://localhost:9443/health' -TimeoutSeconds 1 | Should -BeFalse
  }
}
