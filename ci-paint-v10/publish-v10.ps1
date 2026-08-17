$ErrorActionPreference='Stop'
$branch='build/race-day-live-paint-creator'
git config user.name 'github-actions[bot]';git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git fetch origin $branch
git rebase "origin/$branch"
$releaseDir='paint-creator/releases';New-Item -ItemType Directory -Force $releaseDir|Out-Null
$zip=Join-Path $releaseDir 'MXB_Race_Day_Live_Paint_Creator_Module_v10_0_0.zip';if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $env:MODULE '*') -DestinationPath $zip -Force
$sha=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{version='10.0.0';url='https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/build/race-day-live-paint-creator/paint-creator/releases/MXB_Race_Day_Live_Paint_Creator_Module_v10_0_0.zip';sha256=$sha;notes='v10: BUY & INSTALL now uses verified PiBoSo PaintEd 1.4 CLI to create .pnt files automatically, detects the MX Bikes mods folder including [mods] folder overrides, installs to the correct paint directory, preserves official PiBoSo rider FBX/PSD templates, and hot-refreshes in app.'}|ConvertTo-Json|Set-Content 'paint-creator/latest.json' -Encoding utf8
git add paint-creator;git commit -m 'Publish Paint Creator v10 automatic PNT install [skip ci]'
try{git push origin "HEAD:$branch";if($LASTEXITCODE -ne 0){throw 'initial push failed'}}catch{git fetch origin $branch;git rebase "origin/$branch";git push origin "HEAD:$branch";if($LASTEXITCODE -ne 0){throw 'v10 feed push failed after rebase retry'}}
Write-Host "PUBLISHED_V10_SHA256=$sha"
