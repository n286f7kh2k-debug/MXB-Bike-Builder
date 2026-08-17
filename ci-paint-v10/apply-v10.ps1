$ErrorActionPreference='Stop'
$v10=''
foreach($n in 0..3){
  $p=("ci-paint-v10/part{0:D2}.txt" -f $n)
  $v10 += ((Get-Content -Raw $p) -replace '\s','')
}
$zip=Join-Path $env:RUNNER_TEMP 'paint-v10-patch.zip'
[IO.File]::WriteAllBytes($zip,[Convert]::FromBase64String($v10))
$hash=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if($hash -ne '59528901bea602380eceed0ae4a23a2dfa0f85d95b0934616dc8b125a145cbfc'){throw "v10 patch hash mismatch: $hash"}
Expand-Archive $zip $env:SRC -Force
Write-Host "V10_PATCH_SHA256=$hash"
