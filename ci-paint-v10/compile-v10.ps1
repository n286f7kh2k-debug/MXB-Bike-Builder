$ErrorActionPreference='Stop'
$root=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator'
$all=(Get-ChildItem $root -Recurse -File -Include *.cs,*.xaml,*.csproj | ForEach-Object { Get-Content -Raw $_.FullName }) -join "`n"
foreach($needle in @('10.0.0','PaintEdCliPackService','MxBikesEnvironmentDetector','PACKING WITH PIBOSO PAINTED','InstallPnt','mxb_rider_template.FBX')){if(!$all.Contains($needle)){throw "missing v10 requirement: $needle"}}
$proj=Join-Path $root 'MXBRaceDayLive.PaintCreator.csproj'
dotnet build $proj -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
$module=Join-Path $env:RUNNER_TEMP 'module-v10'
dotnet publish $proj -c Release -r win-x64 --self-contained false -o $module
if($LASTEXITCODE){exit $LASTEXITCODE}
if(!(Test-Path (Join-Path $module 'MXBRaceDayLive.PaintCreator.dll'))){throw 'v10 module missing'}
"MODULE=$module" >> $env:GITHUB_ENV
