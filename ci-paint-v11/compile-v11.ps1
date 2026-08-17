$ErrorActionPreference='Stop'
$root=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator'
function EnsureUsing([string]$file,[string]$usingLine){
  $t=Get-Content -Raw -LiteralPath $file
  if($t -notmatch [regex]::Escape($usingLine)){ Set-Content -LiteralPath $file -Value ($usingLine+"`r`n"+$t) -Encoding utf8 }
}
EnsureUsing (Join-Path $root 'Services\OfficialMxBikesToolchainService.cs') 'using System.IO;'
EnsureUsing (Join-Path $root 'Services\OfficialMxBikesToolchainService.cs') 'using System.Net.Http;'
EnsureUsing (Join-Path $root 'Services\PsdTemplateRegionService.cs') 'using System.IO;'
$all=(Get-ChildItem $root -Recurse -File -Include *.cs,*.xaml,*.csproj | ForEach-Object { Get-Content -Raw $_.FullName }) -join "`n"
foreach($needle in @('11.0.0','PsdTemplateRegionService','PaintTemplateProfiles','COLOR ZONE','SetTemplateZoneColor','UseSourceAlphaAsMask','RiderTemplatePsdPathOverride','GlovesTemplatePsdPathOverride','PaintEdCliPackService','PACKING WITH PIBOSO PAINTED','mxb_rider_template.FBX')){ if(!$all.Contains($needle)){ throw "missing v11 requirement: $needle" } }
$proj=Join-Path $root 'MXBRaceDayLive.PaintCreator.csproj'
dotnet build $proj -c Release
if($LASTEXITCODE){ exit $LASTEXITCODE }
$module=Join-Path $env:RUNNER_TEMP 'module-v11'
dotnet publish $proj -c Release -r win-x64 --self-contained false -o $module
if($LASTEXITCODE){ exit $LASTEXITCODE }
if(!(Test-Path (Join-Path $module 'MXBRaceDayLive.PaintCreator.dll'))){ throw 'v11 module missing' }
"MODULE=$module" >> $env:GITHUB_ENV
Write-Host 'V11_MODULE_COMPILED'