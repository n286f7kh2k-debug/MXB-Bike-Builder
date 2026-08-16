$ErrorActionPreference='Stop'
function Raw([string]$p){ ((Get-Content -Raw $p) -replace '\s','') }
function EnsureUsing([string]$file,[string]$usingLine){
  $text=Get-Content -Raw -LiteralPath $file
  if($text -notmatch [regex]::Escape($usingLine)){
    Set-Content -LiteralPath $file -Value ($usingLine+"`r`n"+$text) -Encoding utf8
  }
}

Write-Host '=== RECONSTRUCT VERIFIED V6 SOURCE ==='
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
$src=Join-Path $env:RUNNER_TEMP 'v6src';Expand-Archive $z $src -Force
$z5=Join-Path $env:RUNNER_TEMP 'v5.zip';[IO.File]::WriteAllBytes($z5,[Convert]::FromBase64String((Raw 'ci-paint-v5/paint-v5-patch.zip.b64')))
if((Get-FileHash $z5 -Algorithm SHA256).Hash.ToLowerInvariant() -ne '3147dc1188d40d0b722f8051fdd6237667bc6971d4c91bb93addcd6b1388a5db'){throw 'v5 hash mismatch'}
Expand-Archive $z5 $src -Force
$clean='';foreach($n in 0..5){$clean+=Raw ("ci-paint-v6-clean/part{0:D2}.txt" -f $n)}
$z6=Join-Path $env:RUNNER_TEMP 'v6-clean.zip';[IO.File]::WriteAllBytes($z6,[Convert]::FromBase64String($clean))
$h=(Get-FileHash $z6 -Algorithm SHA256).Hash.ToLowerInvariant()
if($h -ne '1a73432db443a91413fee528f72cd3eac7e7be728b602e70e5a533c9add6d586'){throw "v6 clean hash mismatch: $h"}
Expand-Archive $z6 $src -Force

# WPF temporary projects do not reliably inherit all implicit usings.
$moduleRoot=Join-Path $src 'src\MXBRaceDayLive.PaintCreator'
foreach($rel in @('Services\RiderGearSetStore.cs','Monetization\ProjectFingerprintService.cs','Services\ObjUvMeshLoader.cs','Services\IGearPreviewModelService.cs','Services\OfficialMxBikesPreviewModelService.cs')){
  EnsureUsing (Join-Path $moduleRoot $rel) 'using System.IO;'
}
EnsureUsing (Join-Path $moduleRoot 'Services\OfficialMxBikesPreviewModelService.cs') 'using System.Net.Http;'
$demoRoot=Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Demo'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorHotUpdateService.cs') 'using System.Net.Http;'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorHotUpdateService.cs') 'using System.IO;'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleLoadContext.cs') 'using System.IO;'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleSession.cs') 'using System.IO;'
EnsureUsing (Join-Path $demoRoot 'PaintCreatorModuleSession.cs') 'using System.Threading;'
EnsureUsing (Join-Path $demoRoot 'MainWindow.xaml.cs') 'using System.IO;'

Write-Host '=== BUILD CONTRACTS / MODULE / HOST ==='
dotnet build (Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Contracts\MXBRaceDayLive.PaintCreator.Contracts.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
dotnet build (Join-Path $src 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
dotnet build (Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Demo\MXBRaceDayLive.PaintCreator.Demo.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}

Write-Host '=== PUBLISH VERSIONED MODULE ==='
$module=Join-Path $env:RUNNER_TEMP 'module-publish'
dotnet publish (Join-Path $src 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj') -c Release -r win-x64 --self-contained false -o $module
if($LASTEXITCODE){exit $LASTEXITCODE}
if(!(Test-Path (Join-Path $module 'MXBRaceDayLive.PaintCreator.dll'))){throw 'module DLL missing'}
$env:MODULE=$module

Write-Host '=== HOT SWAP STATE SMOKE TEST ==='
$test=Join-Path $env:RUNNER_TEMP 'hotswap';New-Item -ItemType Directory -Force $test|Out-Null
$contracts=Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Contracts\MXBRaceDayLive.PaintCreator.Contracts.csproj'
$demo=Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Demo\MXBRaceDayLive.PaintCreator.Demo.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="$contracts"/><ProjectReference Include="$demo"/></ItemGroup></Project>
"@|Set-Content (Join-Path $test 'HotSwap.csproj')
@'
using MXBRaceDayLive.PaintCreator.Contracts;
using MXBRaceDayLive.PaintCreator.Demo;
internal sealed class Services:IPaintCreatorHostServices{public Task<HostPaintOffer> GetExportOfferAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintOffer(r.ProductId,"TEST",1m,"USD"));public Task<HostPaintAuthorization> CheckExportAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintAuthorization(true,"OK"));public Task<HostPaintAuthorization> PurchaseExportAsync(HostPaintExportRequest r,CancellationToken c=default)=>Task.FromResult(new HostPaintAuthorization(true,"OK"));}
internal static class Program{[STAThread]static void Main(){var app=new System.Windows.Application();var module=Environment.GetEnvironmentVariable("MODULE")!;var second=Path.Combine(Path.GetTempPath(),"mxb-v6-module-second-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(second);foreach(var f in Directory.EnumerateFiles(module,"*",SearchOption.AllDirectories)){var rel=Path.GetRelativePath(module,f);var d=Path.Combine(second,rel);Directory.CreateDirectory(Path.GetDirectoryName(d)!);File.Copy(f,d,true);}var root=Path.Combine(Path.GetTempPath(),"mxb-v6-state-"+Guid.NewGuid().ToString("N"));var opts=new PaintCreatorHostOptions(root,"ci-user");var s1=PaintCreatorModuleSession.Load(module,opts,new Services());if(s1.Module.View==null)throw new Exception("first view missing");var state=s1.Module.CaptureState();Console.WriteLine("FIRST="+s1.Module.ModuleVersion+" STATE="+state.Length);var weak=s1.BeginUnload();var collected=PaintCreatorModuleSession.WaitForUnload(weak);var s2=PaintCreatorModuleSession.Load(second,opts,new Services());s2.Module.RestoreState(state);if(s2.Module.View==null)throw new Exception("second view missing");Console.WriteLine("SECOND="+s2.Module.ModuleVersion+" RESTORED=YES ALC_COLLECTED="+collected);s2.Dispose();}}
'@|Set-Content (Join-Path $test 'Program.cs')
$env:MODULE=$module
dotnet run --project (Join-Path $test 'HotSwap.csproj') -c Release | Tee-Object (Join-Path $env:RUNNER_TEMP 'HOT_SWAP_SMOKE_TEST.txt')
if($LASTEXITCODE){exit $LASTEXITCODE}

Write-Host '=== REAL MX BIKES RIDER UV SMOKE TEST ==='
$s=Join-Path $env:RUNNER_TEMP 'viewer-smoke';New-Item -ItemType Directory -Force $s|Out-Null
$lib=Join-Path $src 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><ProjectReference Include="$lib"/></ItemGroup></Project>
"@|Set-Content (Join-Path $s 'Viewer.csproj')
'using MXBRaceDayLive.PaintCreator.Models;using MXBRaceDayLive.PaintCreator.Services;var root=Path.Combine(Path.GetTempPath(),"mxb-v6-viewer-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);var r=await new OfficialMxBikesPreviewModelService().ResolveAsync(PaintTargetType.Rider,new PaintCreatorContext{ProjectRoot=root});if(!r.Ready||string.IsNullOrWhiteSpace(r.ObjPath))throw new Exception("rider model failed: "+r.Status);var m=ObjUvMeshLoader.Load(r.ObjPath);Console.WriteLine($"POSITIONS={m.Positions.Count} TRIANGLES={m.TriangleIndices.Count/3} UVS={m.TextureCoordinates.Count}");if(m.Positions.Count<100||m.TriangleIndices.Count<300||m.TextureCoordinates.Count!=m.Positions.Count)throw new Exception("bad rider UV mesh");'|Set-Content (Join-Path $s 'Program.cs')
dotnet run --project (Join-Path $s 'Viewer.csproj') -c Release | Tee-Object (Join-Path $env:RUNNER_TEMP 'MODEL_VIEWER_SMOKE_TEST.txt')
if($LASTEXITCODE){exit $LASTEXITCODE}

Write-Host '=== PUBLISH SELF CONTAINED HOST ==='
$out=Join-Path $env:RUNNER_TEMP 'host-publish'
dotnet publish (Join-Path $src 'src\MXBRaceDayLive.PaintCreator.Demo\MXBRaceDayLive.PaintCreator.Demo.csproj') -c Release -r win-x64 --self-contained true -p:RuntimeFrameworkVersion=8.0.29 -p:TargetLatestRuntimePatch=false -o $out
if($LASTEXITCODE){exit $LASTEXITCODE}
$bundle=Join-Path $out 'Modules\PaintCreator\6.0.0';New-Item -ItemType Directory -Force $bundle|Out-Null
Copy-Item (Join-Path $module '*') $bundle -Recurse -Force
Copy-Item (Join-Path $env:RUNNER_TEMP 'HOT_SWAP_SMOKE_TEST.txt') $out
Copy-Item (Join-Path $env:RUNNER_TEMP 'MODEL_VIEWER_SMOKE_TEST.txt') $out
if(!(Test-Path (Join-Path $out 'MXB Race Day Live - Paint Creator.exe'))){throw 'host EXE missing'}
if(!(Test-Path (Join-Path $bundle 'MXBRaceDayLive.PaintCreator.dll'))){throw 'bundled module missing'}

Write-Host '=== BUILD UPDATE PACKAGE / MANIFEST ==='
$releaseDir='paint-creator/releases';New-Item -ItemType Directory -Force $releaseDir|Out-Null
$zip=Join-Path $releaseDir 'MXB_Race_Day_Live_Paint_Creator_Module_v6_0_0.zip'
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $module '*') -DestinationPath $zip -Force
$sha=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest=[ordered]@{version='6.0.0';url='https://api.github.com/repos/n286f7kh2k-debug/MXB-Bike-Builder/contents/paint-creator/releases/MXB_Race_Day_Live_Paint_Creator_Module_v6_0_0.zip?ref=build%2Frace-day-live-paint-creator';sha256=$sha;notes='Paint Creator v6: in-app hot update button, automatic update checks, fixed single gear navigation, working Designs library, real MX Bikes rider 3D UV viewer.'}
New-Item -ItemType Directory -Force 'paint-creator'|Out-Null
$manifest|ConvertTo-Json|Set-Content 'paint-creator/latest.json' -Encoding utf8
$verify=Join-Path $env:RUNNER_TEMP 'module-verify';Expand-Archive $zip $verify -Force
if(!(Test-Path (Join-Path $verify 'MXBRaceDayLive.PaintCreator.dll'))){throw 'update ZIP invalid'}
@("MODULE_SHA256=$sha",'HOST_STAYS_OPEN=YES','STATE_CAPTURE_RESTORE=YES','MANUAL_UPDATE_BUTTON=YES','AUTOMATIC_UPDATE_CHECKS=YES')|Set-Content (Join-Path $out 'V6_UPDATE_VALIDATION.txt')

Write-Host '=== FINAL VALIDATION ==='
$exe=Join-Path $out 'MXB Race Day Live - Paint Creator.exe'
(Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()|Set-Content (Join-Path $out 'EXE.sha256')
Get-ChildItem $out|Select-Object Name,Length|Format-Table -AutoSize|Out-File (Join-Path $out 'BUILD_MANIFEST.txt')
"OUT=$out" >> $env:GITHUB_ENV
"MODULE_SHA=$sha" >> $env:GITHUB_ENV