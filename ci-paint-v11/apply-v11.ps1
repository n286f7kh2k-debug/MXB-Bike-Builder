$ErrorActionPreference='Stop'
function Raw([string]$p){ ((Get-Content -Raw -LiteralPath $p) -replace '\s','') }
$b=''
foreach($n in 0..8){ $b += Raw ("ci-paint-v11/part{0:D2}.txt" -f $n) }
$zip=Join-Path $env:RUNNER_TEMP 'paint-v11.zip'
[IO.File]::WriteAllBytes($zip,[Convert]::FromBase64String($b))
$sha=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if($sha -ne 'a955104e65c1628f42ef537f63b2d76c89a146eff3e78061b81518910d19bdd3'){ throw "v11 patch hash mismatch: $sha" }
if([string]::IsNullOrWhiteSpace($env:SRC)){ throw 'SRC is not set; v10 source must be reconstructed first.' }
Expand-Archive $zip $env:SRC -Force
Write-Host "V11_PATCH_SHA256=$sha"
