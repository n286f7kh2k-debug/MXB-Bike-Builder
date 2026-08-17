$ErrorActionPreference='Stop'
$test=Join-Path $env:RUNNER_TEMP 'v11-psd-zones';New-Item -ItemType Directory -Force $test|Out-Null
$lib=Join-Path $env:SRC 'src\MXBRaceDayLive.PaintCreator\MXBRaceDayLive.PaintCreator.csproj'
@"
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="$lib" /></ItemGroup></Project>
"@ | Set-Content (Join-Path $test 'Zones.csproj')
@'
using ImageMagick;
using MXBRaceDayLive.PaintCreator.Models;
using MXBRaceDayLive.PaintCreator.Services;
using System.IO;

var root=Path.Combine(Path.GetTempPath(),"mxb-v11-zones-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
var ctx=new PaintCreatorContext{ProjectRoot=root};
var tools=new OfficialMxBikesToolchainService();
var regions=new PsdTemplateRegionService();

static void RequireNames(IReadOnlyList<string> actual, params string[] required){foreach(var n in required)if(!actual.Any(x=>string.Equals(x,n,StringComparison.OrdinalIgnoreCase)))throw new Exception("missing PSD layer: "+n+" | found: "+string.Join(",",actual));}
static void ValidateMasks(IReadOnlyList<TemplateZoneAsset> masks,int width,int height,int minimum){if(masks.Count<minimum)throw new Exception($"expected at least {minimum} masks, got {masks.Count}");foreach(var m in masks){if(!File.Exists(m.MaskPath)||new FileInfo(m.MaskPath).Length<100)throw new Exception("bad mask: "+m.Zone.DisplayName);using var img=new MagickImage(m.MaskPath);if((int)img.Width!=width||(int)img.Height!=height)throw new Exception($"mask {m.Zone.DisplayName} wrong size {img.Width}x{img.Height}");Console.WriteLine($"ZONE={m.Zone.DisplayName} MASK={Path.GetFileName(m.MaskPath)} SIZE={img.Width}x{img.Height}");}}

var rider=await tools.EnsurePaintTemplateAsync(PaintTargetType.Rider,ctx);
if(rider.Width!=2048||rider.Height!=2048)throw new Exception($"rider PSD wrong size {rider.Width}x{rider.Height}");
var riderNames=regions.ReadLayerNames(rider.PsdPath);RequireNames(riderNames,"TOP","Pants","Knees","UV");
var riderMasks=regions.EnsureZoneMasks(rider,PaintTemplateProfiles.Get(PaintTargetType.Rider));ValidateMasks(riderMasks,2048,2048,3);

var gloves=await tools.EnsurePaintTemplateAsync(PaintTargetType.Gloves,ctx);
if(gloves.Width!=2048||gloves.Height!=1024)throw new Exception($"gloves PSD wrong size {gloves.Width}x{gloves.Height}");
var gloveNames=regions.ReadLayerNames(gloves.PsdPath);RequireNames(gloveNames,"MAIN COLOUR","PALM","SiIDES","THUMB","UV");
var gloveMasks=regions.EnsureZoneMasks(gloves,PaintTemplateProfiles.Get(PaintTargetType.Gloves));ValidateMasks(gloveMasks,2048,1024,4);

// Prove the editor can consume an extracted authoritative PSD mask as a friendly color zone.
var app=new System.Windows.Application();
var editor=new MXBRaceDayLive.PaintCreator.PaintCreatorControl();
var first=riderMasks.First();
var layer=editor.SetTemplateZoneColor(first.Zone,first.MaskPath,"#FF00FF00");
if(!layer.UseSourceAlphaAsMask||!string.Equals(layer.TemplateZoneId,first.Zone.Id,StringComparison.OrdinalIgnoreCase)||layer.Width!=editor.CurrentProject.CanvasWidth||layer.Height!=editor.CurrentProject.CanvasHeight)throw new Exception("PSD zone layer was not created correctly");
var preview=editor.RenderPreviewTexture(512,false);if(preview.PixelWidth<1||preview.PixelHeight<1)throw new Exception("zone preview render failed");
Console.WriteLine($"ZONE_EDITOR_READY RIDER_MASKS={riderMasks.Count} GLOVE_MASKS={gloveMasks.Count} PREVIEW={preview.PixelWidth}x{preview.PixelHeight}");
'@ | Set-Content (Join-Path $test 'Program.cs')
dotnet run --project (Join-Path $test 'Zones.csproj') -c Release
if($LASTEXITCODE){exit $LASTEXITCODE}
