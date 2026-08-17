$ErrorActionPreference='Stop'
$branch='build/race-day-live-paint-creator'
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
# The build can run while another CI helper commit lands on this temporary branch.
# Rebase onto the current remote tip before creating the feed commit so publishing is fast-forward safe.
git fetch origin $branch
git rebase "origin/$branch"

$releaseDir='paint-creator/releases'
New-Item -ItemType Directory -Force $releaseDir|Out-Null
$zip=Join-Path $releaseDir 'MXB_Race_Day_Live_Paint_Creator_Module_v9_0_0.zip'
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $env:MODULE '*') -DestinationPath $zip -Force
$sha=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  version='9.0.0'
  url='https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/build/race-day-live-paint-creator/paint-creator/releases/MXB_Race_Day_Live_Paint_Creator_Module_v9_0_0.zip'
  sha256=$sha
  notes='v9 PiBoSo official toolchain: official mxb_rider_template.FBX 3D UV viewer, rider/glove PSD template profiles, PaintEd integration, preserved UV placement/projects, and in-app hot updating.'
}|ConvertTo-Json|Set-Content 'paint-creator/latest.json' -Encoding utf8

git add paint-creator
git commit -m 'Publish Paint Creator v9 PiBoSo official toolchain [skip ci]'
try {
  git push origin "HEAD:$branch"
  if($LASTEXITCODE -ne 0){throw 'initial push failed'}
} catch {
  # One retry if another harmless branch commit landed during packaging.
  git fetch origin $branch
  git rebase "origin/$branch"
  git push origin "HEAD:$branch"
  if($LASTEXITCODE -ne 0){throw 'v9 feed push failed after rebase retry'}
}
Write-Host "PUBLISHED_V9_SHA256=$sha"
