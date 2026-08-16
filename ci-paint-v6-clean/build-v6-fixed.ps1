$ErrorActionPreference='Stop'
$source=Get-Content -Raw -LiteralPath './ci-paint-v6-clean/build-v6.ps1'
$needle="EnsureUsing (Join-Path `$moduleRoot 'Services\OfficialMxBikesPreviewModelService.cs') 'using System.Net.Http;'"
$insert=@"
EnsureUsing (Join-Path `$moduleRoot 'PaintCreatorModuleEntry.cs') 'using System.IO;'
`$adapter=Join-Path `$moduleRoot 'HostEntitlementAdapter.cs'
`$adapterText=Get-Content -Raw -LiteralPath `$adapter
`$adapterText=`$adapterText.Replace('r.DesignName','r.ProjectName')
Set-Content -LiteralPath `$adapter -Value `$adapterText -Encoding utf8
"@
if(-not $source.Contains($needle)){throw 'Could not locate v6 patch insertion point.'}
$source=$source.Replace($needle,$needle+"`r`n"+$insert)

# Patch the generated smoke-test programs regardless of LF/CRLF in this script.
$hotPattern='using MXBRaceDayLive\.PaintCreator\.Contracts;\r?\nusing MXBRaceDayLive\.PaintCreator\.Demo;'
$hotReplacement="using System.IO;`r`nusing MXBRaceDayLive.PaintCreator.Contracts;`r`nusing MXBRaceDayLive.PaintCreator.Demo;"
$source=[regex]::Replace($source,$hotPattern,$hotReplacement,1)
if($source -notmatch 'using System\.IO;\r?\nusing MXBRaceDayLive\.PaintCreator\.Contracts;'){throw 'Hot-swap smoke-test IO import patch failed.'}

$viewerNeedle="'using MXBRaceDayLive.PaintCreator.Models;using MXBRaceDayLive.PaintCreator.Services;"
$viewerReplacement="'using System.IO;using MXBRaceDayLive.PaintCreator.Models;using MXBRaceDayLive.PaintCreator.Services;"
if(-not $source.Contains($viewerNeedle)){throw 'Could not locate viewer smoke-test source.'}
$source=$source.Replace($viewerNeedle,$viewerReplacement)

$patched=Join-Path $env:RUNNER_TEMP 'build-v6-fixed.ps1'
Set-Content -LiteralPath $patched -Value $source -Encoding utf8
& $patched
exit $LASTEXITCODE