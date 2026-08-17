$ErrorActionPreference='Stop'
function Raw([string]$p){ ((Get-Content -Raw $p) -replace '\s','') }
function EnsureUsing([string]$file,[string]$usingLine){
  $t=Get-Content -Raw -LiteralPath $file
  if($t -notmatch [regex]::Escape($usingLine)){ Set-Content -LiteralPath $file -Value ($usingLine+"`r`n"+$t) -Encoding utf8 }
}
$p01=(Raw 'ci-paint-v4-repair/p01_0.txt')+(Raw 'ci-paint-v4-repair/p01_1.txt')+(Raw 'ci-paint-v4-repair/p01_2.txt')
$p06=(Raw 'ci-paint-v4-repair/p06_0.txt')+(Raw 'ci-paint-v4-repair/p06_1.txt')+(Raw 'ci-paint-v4-repair/p06_2.txt')
$p09=(Raw 'ci-paint-v4-repair/p09s_0.txt')+(Raw 'ci-paint-v4-repair/p09s_1.txt')+(Raw 'ci-paint-v4-repair/p09s_2.txt')+(Raw 'ci-paint-v4-repair/p09s_3.txt')+(Raw 'ci-paint-v4-repair/p09s_4.txt')
$p10=(Raw 'ci-paint-v4-repair/p10s_0.txt')+(Raw 'ci-paint-v4-repair/p10s_1.txt')+(Raw 'ci-paint-v4-repair/p10s_2.txt')+(Raw 'ci-paint-v4-repair/p10s_3.txt')+(Raw 'ci-paint-v4-repair/p10s_4.txt')
$b=$p01
foreach($n in 2..5){$b+=Raw ("ci-paint-v4/part{0:D2}.txt" -f $n)}
$b+=$p06
foreach($n in 7..8){$b+=Raw ("ci-paint-v4/part{0:D2}.txt" -f $n)}
$b+=$p09+$p10
$z=Join-Path $env:RUNNER_TEMP 'v4.zip';[IO.File]::WriteAllBytes($z,[Convert]::FromBase64String($b))
if((Get-FileHash $z -Algorithm SHA256).Hash.ToLowerInvariant() -ne '4d4a4e2c81b4210530d1993da89a859ea02f3c4eb870748de3ef85dabd1bd7c9'){throw 'v4 hash mismatch'}
$src=Join-Path $env:RUNNER_TEMP 'v9src';Expand-Archive $z $src -Force
$z5=Join-Path $env:RUNNER_TEMP 'v5.zip';[IO.File]::WriteAllBytes($z5,[Convert]::FromBase64String((Raw 'ci-paint-v5/paint-v5-patch.zip.b64')));Expand-Archive $z5 $src -Force
$v6='';foreach($n in 0..5){$v6+=Raw ("ci-paint-v6-clean/part{0:D2}.txt" -f $n)};$z6=Join-Path $env:RUNNER_TEMP 'v6.zip';[IO.File]::WriteAllBytes($z6,[Convert]::FromBase64String($v6));Expand-Archive $z6 $src -Force
$v7='';foreach($n in 0..3){$v7+=Raw ("ci-paint-v7/part{0:D2}.txt" -f $n)};$z7=Join-Path $env:RUNNER_TEMP 'v7.zip';[IO.File]::WriteAllBytes($z7,[Convert]::FromBase64String($v7));Expand-Archive $z7 $src -Force
$v8='';foreach($n in 0..3){$v8+=Raw ("ci-paint-v8/part{0:D2}.txt" -f $n)};$z8=Join-Path $env:RUNNER_TEMP 'v8.zip';[IO.File]::WriteAllBytes($z8,[Convert]::FromBase64String($v8));Expand-Archive $z8 $src -Force
$v9=(Raw 'ci-paint-v9s/part00.txt')+(Raw 'ci-paint-v9s/part01.txt')+(Raw 'ci-paint-v9/part01.txt')+(Raw 'ci-paint-v9s/part04.txt')+(Raw 'ci-paint-v9s/part05.txt')+(Raw 'ci-paint-v9s/part06.txt')+(Raw 'ci-paint-v9s/part07.txt')
$z9=Join-Path $env:RUNNER_TEMP 'v9.zip';[IO.File]::WriteAllBytes($z9,[Convert]::FromBase64String($v9))
$h=(Get-FileHash $z9 -Algorithm SHA256).Hash.ToLowerInvariant();if($h -ne 'dddc9fe4c6152953d318ec9b898c6b02b95c12ff0d9d50e6182eb524d8f4f6f5'){throw "v9 patch hash mismatch: $h"};Expand-Archive $z9 $src -Force
$moduleRoot=Join-Path $src 'src\MXBRaceDayLive.PaintCreator'
foreach($rel in @('Services\RiderGearSetStore.cs','Monetization\ProjectFingerprintService.cs','Services\ObjUvMeshLoader.cs','Services\IGearPreviewModelService.cs','Services\OfficialMxBikesPreviewModelService.cs','Services\OfficialMxBikesToolchainService.cs','PaintCreatorModuleEntry.cs')){EnsureUsing (Join-Path $moduleRoot $rel) 'using System.IO;'}
$toolchain=Join-Path $moduleRoot 'Services\OfficialMxBikesToolchainService.cs'
EnsureUsing $toolchain 'using System.Net.Http;'
$tt=Get-Content -Raw $toolchain
$tt=$tt.Replace('https://www.mx-bikes.com/downloads/painted.zip','https://www.kartracing-pro.com/downloads/painted.zip')
Set-Content $toolchain $tt -Encoding utf8
$adapter=Join-Path $moduleRoot 'HostEntitlementAdapter.cs';$at=Get-Content -Raw $adapter;$at=$at.Replace('r.DesignName','r.ProjectName');Set-Content $adapter $at -Encoding utf8
$demoRoot=Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Demo'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorHotUpdateService.cs') 'using System.Net.Http;';EnsureUsing (Join-Path $demoRoot 'PaintCreatorHotUpdateService.cs') 'using System.IO;';EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleLoadContext.cs') 'using System.IO;';EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleSession.cs') 'using System.IO;';EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleSession.cs') 'using System.Threading;';EnsureUsing (Join-Path $demoRoot 'MainWindow.xaml.cs') 'using System.IO;'
"SRC=$src" >> $env:GITHUB_ENV
Write-Host "V9_SOURCE_SHA=$h"
