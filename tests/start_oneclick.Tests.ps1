$root = Split-Path -Parent $PSScriptRoot
. "$root/tools/start_oneclick.ps1"

Describe 'Wait-BackendHealth' {
    It 'returns true when health eventually ok' {
        $call = 0
        Mock -CommandName Test-NetConnection { @{ TcpTestSucceeded = $true } }
        Mock -CommandName Invoke-WebRequest {
            $script:call++
            if ($script:call -lt 2) { throw 'not ready' }
            @{ StatusCode = 200 }
        }
        Wait-BackendHealth -TimeoutSeconds 5 | Should -BeTrue
    }
}
