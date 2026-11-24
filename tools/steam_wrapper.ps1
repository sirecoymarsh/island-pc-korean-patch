param([Parameter(ValueFromRemainingArguments = $true)][string[]]$SteamCommand)
# Steam launch-option wrapper for ISLAND test copies (island-steam-ko).
# Steam starts this with its own environment (SteamAppId etc.); we start the copy named in
# steam_wrapper.json with the copy folder as working directory. mode=original runs %command%.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'steam_wrapper.log'
function Log($m) { try { Add-Content -LiteralPath $log -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' ' + $m) -Encoding UTF8 } catch {} }
try {
    $cfg = Get-Content -LiteralPath (Join-Path $here 'steam_wrapper.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfg.mode -eq 'original' -or -not $cfg.game) {
        Log ("original command: " + ($SteamCommand -join ' '))
        $exe = $SteamCommand[0]; $rest = @(); if ($SteamCommand.Count -gt 1) { $rest = $SteamCommand[1..($SteamCommand.Count - 1)] }
        $p = Start-Process -FilePath $exe -ArgumentList $rest -WorkingDirectory (Split-Path -Parent $exe) -PassThru
        $p.WaitForExit(); exit $p.ExitCode
    }
    $game = [IO.Path]::GetFullPath($cfg.game)
    $exe = Join-Path $game 'ISLAND.exe'
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.WorkingDirectory = $game
    $psi.UseShellExecute = $false
    if ($cfg.env) { foreach ($k in $cfg.env.PSObject.Properties) { $psi.EnvironmentVariables[$k.Name] = [string]$k.Value } }
    $p = [Diagnostics.Process]::Start($psi)
    Log ("started pid=" + $p.Id + " game=" + $game + " steamappid=" + $env:SteamAppId)
    $p.WaitForExit()
    Log ("exited pid=" + $p.Id + " code=" + $p.ExitCode)
    exit $p.ExitCode
} catch {
    Log ("error: " + $_.Exception.Message)
    exit 1
}
