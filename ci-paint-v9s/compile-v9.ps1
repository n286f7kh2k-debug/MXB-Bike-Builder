$ErrorActionPreference='Stop'
$root=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator'
$all=(Get-ChildItem $root -Recurse -File -Include *.cs,*.xaml,*.csproj | ForEach-Object { Get-Content -Raw $_.FullName }) -join "`n"
foreach($needle in @('rider.psd','mxb_rider_template.FBX','painted.zip','AuthoritativeTemplatePsdPath','PIBOSO RIDER.PSD','Magick.NET-Q8-AnyCPU')){if(!$all.Contains($needle)){throw "missing PiBoSo integration requirement: $needle"}}
$proj=Join-Path $root 'MXBRaceDayLive.PaintCreator.csproj';dotnet build $proj -c Release;if($LASTEXITCODE){exit $LASTEXITCODE}
$module=Join-Path $env:RUNNER_TEMP 'module-v9';dotnet publish $proj -c Release -r win-x64 --self-contained false -o $module;if($LASTEXITCODE){exit $LASTEXITCODE}
if(!(Test-Path (Join-Path $module 'MXBRaceDayLive.PaintCreator.dll'))){throw 'v9 module missing'}
"MODULE=$module" >> $env:GITHUB_ENV
